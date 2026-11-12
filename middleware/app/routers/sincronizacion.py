"""
Endpoints de sincronización real con Moodle UTA (exclusivos del rol DOCENTE).

  POST /api/sincronizacion                 Extrae cursos, estudiantes y notas desde Moodle
  GET  /api/sincronizacion                 Último resultado sincronizado (cursos del docente)
  GET  /api/cursos/{course_id}/estudiantes Estudiantes y notas de un curso (403 si no es su curso)
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.routers.auth import get_current_user
from app.routers.logs import append_log
from app.services import sync_service
from app.services.moodle_client import MoodleError

router = APIRouter(tags=["Sincronización Moodle"])


def get_current_docente(user: dict = Depends(get_current_user)) -> dict:
    if user.get("rol") != "DOCENTE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso exclusivo para el rol DOCENTE.",
        )
    return user


@router.post("/sincronizacion")
async def sincronizar_moodle(docente: dict = Depends(get_current_docente)):
    try:
        estado = await sync_service.sincronizar()
    except MoodleError as ex:
        append_log(
            tipo_proceso="SINCRONIZACION",
            estado="ERROR",
            mensaje=f"Fallo al sincronizar con Moodle: {ex}",
            detalle={},
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(ex))

    respuesta = sync_service.respuesta_para_docente(docente["email"])
    log = append_log(
        tipo_proceso="SINCRONIZACION",
        estado="EXITO",
        mensaje=(
            f"Sincronización Moodle completada en {estado['duracion_ms']} ms: "
            f"{respuesta['total_cursos']} cursos, {respuesta['total_estudiantes']} estudiantes."
        ),
        detalle={"cursos": respuesta["total_cursos"], "estudiantes": respuesta["total_estudiantes"]},
    )
    return {"status": "success", "duracion_ms": estado["duracion_ms"], "log_id": log["id"], **respuesta}


@router.get("/sincronizacion")
async def estado_sincronizacion(docente: dict = Depends(get_current_docente)):
    return sync_service.respuesta_para_docente(docente["email"])


@router.get("/cursos/{course_id}/estudiantes")
async def estudiantes_del_curso(course_id: int, docente: dict = Depends(get_current_docente)):
    curso = next((c for c in sync_service.SYNC_STATE["cursos"] if c["id"] == course_id), None)
    if curso is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Curso {course_id} no sincronizado. Ejecute la sincronización con Moodle.",
        )
    if docente["email"].strip().lower() not in curso["docentes"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos sobre este curso: no está matriculado como docente en Moodle.",
        )
    return {**sync_service.resumen_curso(curso), "estudiantes": curso["estudiantes"]}
