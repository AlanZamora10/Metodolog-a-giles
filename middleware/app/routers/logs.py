"""
Auditoría del sistema (HU-16 / RN-18) persistida en la tabla `logs_sistema` (Sprint 3).

append_log() es el único punto de escritura: sincronizaciones, atención/cierre de alertas,
origen del diagnóstico (ollama_slm vs motor_heuristico_hu11b) y publicaciones.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends

from app import database, repositories
from app.routers.auth import get_current_docente
from app.schemas.academic import AlertResponse, SystemLogResponse

logger = logging.getLogger("edumonitor.logs")

router = APIRouter(tags=["Logs y Alertas"])


def append_log(tipo_proceso: str, estado: str, mensaje: str, detalle: Optional[Dict[str, Any]] = None,
               tiempo_ejecucion_ms: Optional[int] = None) -> Dict[str, Any]:
    """Inserta un evento de auditoría en logs_sistema y lo devuelve (con id y timestamp)."""
    return repositories.insert_log(tipo_proceso, estado, mensaje, detalle, tiempo_ejecucion_ms)


@database.on_ready
def registrar_inicio(engine) -> None:
    repositories.insert_log(
        "INICIO_SERVICIO", "INFO" if database.backend_name() == "postgresql" else "ADVERTENCIA",
        f"Middleware iniciado. Persistencia: {database.backend_name()}.",
        {"motor": database.backend_name()}, engine=engine,
    )


@router.get("/logs", response_model=List[SystemLogResponse])
async def list_logs(docente: dict = Depends(get_current_docente)):
    """
    Retorna los registros de sincronización, análisis y alertas del sistema (HU-16) desde PostgreSQL.
    """
    return [
        {**log, "timestamp": log["timestamp"] or "", "detalle": log.get("detalle") or {}}
        for log in repositories.list_logs()
    ]


@router.get("/alerts", response_model=List[AlertResponse])
async def list_alerts(docente: dict = Depends(get_current_docente)):
    """
    Vista resumida (heredada de HU-08) de las alertas tempranas de los cursos del docente.
    """
    correo = docente["email"].lower()
    return [
        {
            "id": a["id"],
            "id_number": a["id_number"],
            "nombres": a["nombres"],
            "nivel": a["nivel"],
            "unidad_critica": a.get("unidad_critica") or "",
            "motivo": a["motivo"],
            "diagnostico_ia": a.get("diagnostico_ia") or "",
            "accion_sugerida": a.get("tipo_accion_sugerida") or "",
        }
        for a in repositories.list_alertas()
        if correo in (a.get("curso_docentes") or [])
    ]
