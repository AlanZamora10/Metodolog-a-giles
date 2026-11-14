"""
Cursos del docente y resumen de métricas (HU-03). Exclusivo del rol DOCENTE (Sprint 3).

Los cursos sincronizados desde Moodle (persistidos en PostgreSQL) tienen prioridad; el dataset
heredado del Sprint 1 (MAT1 / MAT2) sólo se usa si el docente aún no tiene cursos sincronizados.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app import repositories
from app.routers.auth import get_current_docente
from app.routers.students import STUDENTS_STORE, _build_student_response, respuesta_sincronizada
from app.schemas.academic import CourseSummary
from app.services import reporte_service, sync_service

router = APIRouter(prefix="/courses", tags=["Cursos"])

_CURSOS_HEREDADOS = {"MAT1": "Metodologías Ágiles", "MAT2": "Ingeniería de Software"}


def _resumen(codigo: str, nombre: str, estudiantes) -> CourseSummary:
    total = len(estudiantes)
    criticos = sum(1 for s in estudiantes if s.nivel_riesgo == "CRITICO")
    return CourseSummary(
        materia_codigo=codigo,
        materia_nombre=nombre,
        promedio_general=round(sum(s.nota_final for s in estudiantes) / total, 2) if total else 0.0,
        total_estudiantes=total,
        estudiantes_criticos=criticos,
        estudiantes_en_riesgo=sum(1 for s in estudiantes if s.nivel_riesgo == "EN_RIESGO"),
        estudiantes_aceptables=sum(1 for s in estudiantes if s.nivel_riesgo == "ACEPTABLE"),
        alertas_detectadas=sum(1 for s in estudiantes if s.regla_alerta) if any(s.curso for s in estudiantes)
        else criticos,
        estudiantes=estudiantes,
    )


@router.get("/MAT1/summary", response_model=CourseSummary)
async def get_mat1_summary(docente: dict = Depends(get_current_docente)):
    """
    Resumen general de métricas del curso MAT1 (Panel Mockup 1).
    """
    return await get_course_summary("MAT1", docente)


@router.get("/{course_code}/summary", response_model=CourseSummary)
async def get_course_summary(course_code: str, docente: dict = Depends(get_current_docente)):
    """
    Resumen de métricas por código de curso: shortname de Moodle (p. ej. SOF-POO-A) o MAT1/MAT2 heredados.
    403 si el curso existe pero el docente no es profesor del curso en Moodle.
    """
    codigo = course_code.upper()
    curso = next((c for c in sync_service.SYNC_STATE["cursos"] if c["shortname"].upper() == codigo), None)
    if curso is not None:
        if docente["email"].strip().lower() not in curso["docentes"]:
            raise HTTPException(status_code=403, detail="No tiene permisos sobre este curso.")
        return _resumen(curso["shortname"], curso["fullname"],
                        [respuesta_sincronizada(e, curso) for e in curso["estudiantes"]])

    if codigo in _CURSOS_HEREDADOS:
        return _resumen(codigo, _CURSOS_HEREDADOS[codigo], [_build_student_response(st) for st in STUDENTS_STORE])

    raise HTTPException(status_code=404, detail=f"Curso '{course_code}' no encontrado. Sincronice con Moodle.")


def curso_autorizado(course_id: int, docente: dict) -> dict:
    """Curso sincronizado (por ID de Moodle) del que el docente es profesor; 404 / 403 en otro caso."""
    curso = next((c for c in sync_service.SYNC_STATE["cursos"] if c["id"] == course_id), None)
    if curso is None:
        raise HTTPException(status_code=404, detail=f"Curso {course_id} no sincronizado. Sincronice con Moodle.")
    if docente["email"].strip().lower() not in curso["docentes"]:
        raise HTTPException(status_code=403, detail="No tiene permisos sobre este curso.")
    return curso


@router.get("/{course_id}/reporte")
async def reporte_curso(
    course_id: int,
    formato: str = Query("json", pattern="^(json|md)$", description="json (React) o md (descarga Markdown)"),
    docente: dict = Depends(get_current_docente),
):
    """
    Informe del curso: período, métricas, distribución de estados (cero, sin entrega, pendiente),
    alertas, hallazgos, recomendaciones y fecha de la última sincronización con Moodle.
    """
    curso = curso_autorizado(course_id, docente)
    reporte = reporte_service.construir_reporte(
        curso, repositories.list_alertas(course_id=course_id), sync_service.SYNC_STATE.get("ultima_sincronizacion"))
    if formato == "md":
        return PlainTextResponse(
            reporte_service.reporte_markdown(reporte), media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="informe_{curso["shortname"]}.md"'},
        )
    return reporte


@router.get("")
async def list_courses(docente: dict = Depends(get_current_docente)):
    """
    Cursos del docente sincronizados desde Moodle; si aún no hay sincronización, las 2 materias de HU-01.
    """
    sincronizados = sync_service.cursos_del_docente(docente["email"])
    if sincronizados:
        return [
            {
                **sync_service.resumen_curso(c),
                "codigo": c["shortname"],
                "nombre": c["fullname"],
                "carrera": "Ingeniería de Software - FISEI",
                "docente": docente.get("nombres"),
                "parciales": [1, 2],
                "unidades": ["Unidad 1", "Unidad 2", "Unidad 3", "Unidad 4"],
            }
            for c in sincronizados
        ]
    return [
        {
            "codigo": codigo,
            "nombre": nombre,
            "carrera": "Ingeniería de Software - FISEI",
            "docente": docente.get("nombres"),
            "parciales": [1, 2],
            "unidades": ["Unidad 1", "Unidad 2", "Unidad 3", "Unidad 4"],
        }
        for codigo, nombre in _CURSOS_HEREDADOS.items()
    ]
