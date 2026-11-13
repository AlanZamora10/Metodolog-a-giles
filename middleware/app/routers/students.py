"""
Estudiantes con nota ponderada (HU-03 / HU-04). Exclusivo del rol DOCENTE (Sprint 3).

Fuente de datos:
  1. Sincronización real con Moodle persistida en PostgreSQL (cursos donde el docente es profesor).
  2. Si el docente aún no tiene cursos sincronizados: dataset heredado del Sprint 1 (HU-01, MAT1).
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.auth import get_current_docente
from app.schemas.academic import WeightedGradeResponse
from app.services import sync_service
from app.services.grade_calculator import GradeCalculator

router = APIRouter(prefix="/students", tags=["Estudiantes"])

# Dataset heredado del Sprint 1 (HU-01), usado sólo como respaldo sin sincronización
STUDENTS_STORE = [
    {
        "id_number": "U-03",
        "nombres": "Estudiante A",
        "email": "estudiante.a@uta.edu.ec",
        "autonomo": 8.00,
        "tareas": 8.00,
        "pae": 8.00,
        "pendiente": 0.350,
        "probabilidad_aprobacion": 92,
        "notas_actividades": {
            "MAT1-P1-U1-T1": 8.0,
            "MAT1-P1-U2-T2": 8.0,
            "MAT1-P1-U2-T3": 8.0,
            "MAT1-P1-U3-T4": 8.0,
            "MAT1-P1-U4-T5": 8.0
        }
    },
    {
        "id_number": "U-04",
        "nombres": "Estudiante B",
        "email": "estudiante.b@uta.edu.ec",
        "autonomo": 8.50,
        "tareas": 8.50,
        "pae": 8.50,
        "pendiente": 0.050,
        "probabilidad_aprobacion": 95,
        "notas_actividades": {
            "MAT1-P1-U1-T1": 8.5,
            "MAT1-P1-U2-T2": 8.5,
            "MAT1-P1-U2-T3": 8.5,
            "MAT1-P1-U3-T4": 8.5,
            "MAT1-P1-U4-T5": 8.5
        }
    },
    {
        "id_number": "U-05",
        "nombres": "Estudiante C",
        "email": "estudiante.c@uta.edu.ec",
        "autonomo": 3.50,
        "tareas": 3.00,
        "pae": 4.00,
        "pendiente": -0.650,
        "probabilidad_aprobacion": 22,
        "notas_actividades": {
            "MAT1-P1-U1-T1": 6.0,
            "MAT1-P1-U2-T2": 2.0,
            "MAT1-P1-U2-T3": 2.0,
            "MAT1-P1-U3-T4": 4.0,
            "MAT1-P1-U4-T5": 4.0
        }
    },
    {
        "id_number": "U-06",
        "nombres": "Estudiante D",
        "email": "estudiante.d@uta.edu.ec",
        "autonomo": 4.50,
        "tareas": 4.00,
        "pae": 5.00,
        "pendiente": -0.380,
        "probabilidad_aprobacion": 38,
        "notas_actividades": {
            "MAT1-P1-U1-T1": 3.5,
            "MAT1-P1-U2-T2": 5.5,
            "MAT1-P1-U2-T3": 4.0,
            "MAT1-P1-U3-T4": 4.0,
            "MAT1-P1-U4-T5": 5.0
        }
    },
    {
        "id_number": "U-07",
        "nombres": "Estudiante E",
        "email": "estudiante.e@uta.edu.ec",
        "autonomo": 8.00,
        "tareas": 7.00,
        "pae": 7.67,
        "pendiente": 0.280,
        "probabilidad_aprobacion": 88,
        "notas_actividades": {
            "MAT1-P1-U1-T1": 8.0,
            "MAT1-P1-U2-T2": 8.0,
            "MAT1-P1-U2-T3": 7.0,
            "MAT1-P1-U3-T4": 7.0,
            "MAT1-P1-U4-T5": 7.6
        }
    },
    {
        "id_number": "U-08",
        "nombres": "Estudiante F",
        "email": "estudiante.f@uta.edu.ec",
        "autonomo": 6.50,
        "tareas": 6.00,
        "pae": 6.00,
        "pendiente": -0.100,
        "probabilidad_aprobacion": 62,
        "notas_actividades": {
            "MAT1-P1-U1-T1": 7.0,
            "MAT1-P1-U2-T2": 6.0,
            "MAT1-P1-U2-T3": 6.0,
            "MAT1-P1-U3-T4": 6.0,
            "MAT1-P1-U4-T5": 6.0
        }
    },
    {
        "id_number": "U-09",
        "nombres": "Estudiante G",
        "email": "estudiante.g@uta.edu.ec",
        "autonomo": 8.50,
        "tareas": 8.00,
        "pae": 8.70,
        "pendiente": 0.420,
        "probabilidad_aprobacion": 94,
        "notas_actividades": {
            "MAT1-P1-U1-T1": 8.5,
            "MAT1-P1-U2-T2": 8.5,
            "MAT1-P1-U2-T3": 8.0,
            "MAT1-P1-U3-T4": 8.0,
            "MAT1-P1-U4-T5": 8.7
        }
    }
]


def _build_student_response(item: dict) -> WeightedGradeResponse:
    nota_final = GradeCalculator.calculate_weighted_grade(
        autonomo=item["autonomo"],
        tareas=item["tareas"],
        pae=item["pae"]
    )
    nivel = GradeCalculator.classify_risk(nota_final, item.get("pendiente"))
    
    # Determinar etiqueta de tendencia según la pendiente
    pendiente = item.get("pendiente", 0.0)
    if pendiente > 0.25:
        tendencia = "SUBE"
    elif pendiente < -0.25:
        tendencia = "BAJA"
    else:
        tendencia = "ESTABLE"

    return WeightedGradeResponse(
        id_number=item["id_number"],
        nombres=item["nombres"],
        email=item["email"],
        autonomo=item["autonomo"],
        tareas=item["tareas"],
        pae=item["pae"],
        nota_final=nota_final,
        nivel_riesgo=nivel,
        tendencia=tendencia,
        pendiente=pendiente,
        probabilidad_aprobacion=item.get("probabilidad_aprobacion", 50),
        notas_actividades=item.get("notas_actividades", {})
    )


def respuesta_sincronizada(est: Dict[str, Any], curso: Dict[str, Any]) -> WeightedGradeResponse:
    """Estudiante de un curso sincronizado desde Moodle -> WeightedGradeResponse."""
    return WeightedGradeResponse(
        id_number=est["id_number"],
        nombres=est["nombres"] or est["id_number"],
        email=est.get("email") or "",
        autonomo=est["acd"] or 0.0,
        tareas=est["tareas"] or 0.0,
        pae=est["pae"] or 0.0,
        nota_final=est["nota_final"],
        nivel_riesgo=est["nivel_riesgo"],
        tendencia=est.get("tendencia", "ESTABLE"),
        pendiente=est.get("pendiente", 0.0),
        probabilidad_aprobacion=est.get("probabilidad_aprobacion", 50),
        notas_actividades={a["id_number"]: a["nota"] for a in est.get("actividades", []) if a["nota"] is not None},
        curso=curso["shortname"],
        regla_alerta=est.get("regla_alerta"),
    )


def _cursos_filtrados(docente: dict, curso: Optional[str]) -> List[Dict[str, Any]]:
    cursos = sync_service.cursos_del_docente(docente["email"])
    if curso:
        cursos = [c for c in cursos if c["shortname"].upper() == curso.upper()]
    return cursos


@router.get("", response_model=List[WeightedGradeResponse])
async def list_students(curso: Optional[str] = Query(None, description="Shortname del curso, p. ej. SOF-POO-A"),
                        docente: dict = Depends(get_current_docente)):
    """
    Lista los estudiantes (uno por curso) con su nota ponderada, nivel de riesgo y tendencia.
    """
    if sync_service.cursos_del_docente(docente["email"]):
        return [respuesta_sincronizada(e, c) for c in _cursos_filtrados(docente, curso) for e in c["estudiantes"]]
    return [_build_student_response(st) for st in STUDENTS_STORE]


@router.get("/{id_number}", response_model=WeightedGradeResponse)
async def get_student_detail(id_number: str, curso: Optional[str] = Query(None),
                             docente: dict = Depends(get_current_docente)):
    """
    Obtiene el detalle individual de un estudiante con desglose de actividades.
    """
    if sync_service.cursos_del_docente(docente["email"]):
        for c in _cursos_filtrados(docente, curso):
            for e in c["estudiantes"]:
                if e["id_number"].upper() == id_number.upper():
                    return respuesta_sincronizada(e, c)
    else:
        for st in STUDENTS_STORE:
            if st["id_number"].upper() == id_number.upper():
                return _build_student_response(st)
    raise HTTPException(status_code=404, detail=f"Estudiante con ID '{id_number}' no encontrado.")
