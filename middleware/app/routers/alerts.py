"""
==============================================================================
ROUTER: CENTRO DE ALERTAS TEMPRANAS Y REFUERZOS DIDÁCTICOS (HU-05 / SPRINT 3)
FISEI - Universidad Técnica de Ambato
==============================================================================
Cumple con las reglas de negocio:
  - RN-12: Regla R1 (Nota Crítica < 5.0)
  - RN-13: Regla R2 (Descenso de notas entre unidades -pendiente < -0.25- y promedio < 7.0)
  - RN-14: Ciclo de vida ABIERTA -> ATENDIDA -> PUBLICADO o CERRADA (RESUELTA si deja de cumplir la regla)
  - RN-15: Desacoplamiento determinista: el cálculo se hace en código/SQL, IA redacta
  - RN-16: Timeout de 10s para el agente con fallback automático a plantilla
  - RN-17: Confirmación explícita obligatoria antes de publicar en Moodle
  - RN-18: Trazabilidad en Auditoría (logs_sistema)

Sprint 3: las alertas se generan al sincronizar (sync_service) y viven en `alertas_tempranas`;
los borradores de refuerzo, en la tabla `refuerzos`. Todas las rutas exigen JWT de DOCENTE y sólo
exponen alertas de cursos donde el docente es profesor en Moodle (403 en otro caso).
==============================================================================
"""

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app import repositories
from app.routers.auth import get_current_docente
from app.routers.logs import append_log

router = APIRouter(tags=["Centro de Alertas y Refuerzos"])

AGENT_HOST = os.getenv("AGENT_HOST") or os.getenv("AGENT_URL", "http://agent:8001")
AGENT_TIMEOUT_SECONDS = float(os.getenv("AGENT_INFERENCE_TIMEOUT_SECONDS", "10.0"))
_PATRON_UNIDAD = re.compile(r"^U(\d+)-", re.IGNORECASE)


class AlertaOut(BaseModel):
    id: int
    curso_id: Optional[int] = None
    curso_codigo: str
    curso_nombre: str
    id_number: str
    nombres: str
    email: str
    regla: str
    nivel: str
    nota_promedio: float
    pendiente: Optional[float] = None
    evidencia: str
    unidad_critica: Optional[str] = None
    tema_critico: Optional[str] = None
    estado: str
    diagnostico_ia: Optional[str] = None
    tipo_accion_sugerida: Optional[str] = None
    fecha_creacion: Optional[str] = None
    fecha_actualizacion: Optional[str] = None
    refuerzo_id: Optional[int] = None


class PublicarRefuerzoReq(BaseModel):
    confirmado: bool = Field(..., description="Confirmación explícita del docente (RN-17)")
    titulo: Optional[str] = None
    instrucciones: Optional[str] = None


def _alerta_out(a: Dict[str, Any]) -> Dict[str, Any]:
    return AlertaOut(
        id=a["id"], curso_id=a.get("curso_id"), curso_codigo=a["curso_codigo"], curso_nombre=a["curso_nombre"],
        id_number=a["id_number"], nombres=a["nombres"], email=a["email"], regla=a["regla"] or "",
        nivel=a["nivel"], nota_promedio=a.get("nota_final") or 0.0, pendiente=a.get("pendiente"),
        evidencia=a["motivo"], unidad_critica=a.get("unidad_critica"), tema_critico=a.get("tema_critico"),
        estado=a.get("estado") or "ABIERTA", diagnostico_ia=a.get("diagnostico_ia"),
        tipo_accion_sugerida=a.get("tipo_accion_sugerida"), fecha_creacion=a.get("fecha_alerta"),
        fecha_actualizacion=a.get("fecha_actualizacion"), refuerzo_id=a.get("refuerzo_id"),
    ).model_dump()


def _es_docente_del_curso(alerta: Dict[str, Any], docente: dict) -> bool:
    return docente["email"].strip().lower() in (alerta.get("curso_docentes") or [])


def _alerta_autorizada(alerta_id: int, docente: dict) -> Dict[str, Any]:
    alerta = repositories.get_alerta(alerta_id)
    if not alerta or not alerta.get("regla"):
        raise HTTPException(status_code=404, detail="Alerta no encontrada.")
    if not _es_docente_del_curso(alerta, docente):
        raise HTTPException(status_code=403, detail="No tiene permisos sobre el curso de esta alerta.")
    return alerta


@router.get("/alertas", response_model=List[AlertaOut])
async def list_alertas(
    course_id: Optional[int] = Query(None, description="ID del curso en Moodle"),
    estado: Optional[str] = Query(None, description="ABIERTA, ATENDIDA, PUBLICADO, CERRADA o RESUELTA"),
    docente: dict = Depends(get_current_docente),
):
    """
    Lista las alertas R1/R2 generadas al sincronizar, sólo de los cursos del docente.
    """
    return [
        _alerta_out(a) for a in repositories.list_alertas(course_id=course_id, estado=estado)
        if _es_docente_del_curso(a, docente)
    ]


@router.get("/alertas/{alerta_id}", response_model=AlertaOut)
async def get_alerta(alerta_id: int, docente: dict = Depends(get_current_docente)):
    """
    Obtiene el detalle de una alerta académica por su identificador.
    """
    return _alerta_out(_alerta_autorizada(alerta_id, docente))


def _notas_para_agente(alerta: Dict[str, Any]) -> Dict[str, float]:
    """Notas en el formato [CURSO]-[PARCIAL]-[UNIDAD]-[ACTIVIDAD] que espera el motor heurístico."""
    prefijo = f"{alerta['curso_codigo']}-"
    notas: Dict[str, float] = {}
    for id_normalizado, nota in repositories.notas_actividades(alerta["estudiante_id"], alerta["materia_id"]):
        actividad = id_normalizado[len(prefijo):] if id_normalizado.startswith(prefijo) else id_normalizado
        match = _PATRON_UNIDAD.match(actividad)
        parcial = 1 if not match or int(match.group(1)) <= 2 else 2
        notas[f"C{alerta['materia_id']}-P{parcial}-{actividad}"] = nota
    return notas


@router.post("/alertas/{alerta_id}/atender", response_model=Dict[str, Any])
async def atender_alerta(alerta_id: int, docente: dict = Depends(get_current_docente)):
    """
    Atiende una alerta académica:
      1. Valida el estado (ABIERTA o ATENDIDA) -> ATENDIDA (RN-14).
      2. Invoca al agente de IA (Ollama / fallback heurístico) para redactar el refuerzo.
      3. Guarda el borrador en `refuerzos` y registra el evento en auditoría.
    """
    alerta = _alerta_autorizada(alerta_id, docente)
    if alerta["estado"] not in ("ABIERTA", "ATENDIDA"):
        raise HTTPException(
            status_code=409,
            detail=f"La alerta se encuentra {alerta['estado']} y no puede atenderse.",
        )

    agente_data = await consultar_agente_ia(
        id_number=alerta["id_number"],
        nombres=alerta["nombres"],
        nota_final=alerta.get("nota_final") or 0.0,
        notas_actividades=_notas_para_agente(alerta),
        unidad_sugerida=alerta.get("unidad_critica"),
    )
    origen = str(agente_data.get("fuente", "motor_heuristico_hu11b"))
    diagnostico = agente_data.get("diagnostico", "")
    accion = agente_data.get("tipo_accion_sugerida") or "Tarea de refuerzo pedagógico"
    unidad = agente_data.get("unidad_critica") or alerta.get("unidad_critica") or "la unidad crítica"

    refuerzo = repositories.upsert_refuerzo(alerta_id, {
        "titulo": f"Refuerzo: {accion} — {alerta['curso_codigo']}"[:200],
        "descripcion": diagnostico,
        "instrucciones": (f"{diagnostico} Revise el material de {unidad}, resuelva la guía de ejercicios y "
                          f"entregue su desarrollo en Moodle UTA dentro de los próximos 7 días."),
        "actividades": [f"Revisión del material de {unidad}", "Resolución de ejercicios guiados",
                        "Entrega del desarrollo en Moodle UTA"],
        "origen": origen.upper(),
        "estado": "BORRADOR",
    })
    repositories.update_alerta(alerta_id, {
        "estado": "ATENDIDA", "diagnostico_ia": diagnostico, "tipo_accion_sugerida": accion[:100],
    })

    append_log(
        tipo_proceso="ATENCION_ALERTA",
        estado="EXITO",
        mensaje=f"Alerta #{alerta_id} ({alerta['regla']}) atendida para {alerta['nombres']}. Origen: {origen}.",
        detalle={"alerta_id": alerta_id, "refuerzo_id": refuerzo["id"], "origen": origen,
                 "curso": alerta["curso_codigo"], "regla": alerta["regla"]},
    )

    return {
        "status": "success",
        "mensaje": "Alerta atendida con éxito y borrador de refuerzo generado.",
        "alerta": _alerta_out(repositories.get_alerta(alerta_id)),
        "refuerzo": refuerzo,
        "diagnostico": agente_data,
    }


@router.patch("/alertas/{alerta_id}/cerrar", response_model=Dict[str, Any])
async def cerrar_alerta(alerta_id: int, docente: dict = Depends(get_current_docente)):
    """
    Cierra una alerta que ya no es relevante (RN-14):
      - Pasa a estado terminal CERRADA (no se reabre).
      - Retorna 409 si ya estaba CERRADA.
      - Registra la acción CERRAR_ALERTA en auditoría.
    """
    alerta = _alerta_autorizada(alerta_id, docente)
    if alerta["estado"] == "CERRADA":
        raise HTTPException(status_code=409, detail="La alerta ya se encuentra en estado CERRADA.")

    repositories.update_alerta(alerta_id, {
        "estado": "CERRADA", "resuelto": True, "fecha_resolucion": datetime.now(timezone.utc),
    })
    append_log(
        tipo_proceso="CERRAR_ALERTA",
        estado="EXITO",
        mensaje=f"Alerta #{alerta_id} cerrada por el docente (estado terminal CERRADA).",
        detalle={"alerta_id": alerta_id, "estudiante": alerta["nombres"], "curso": alerta["curso_codigo"]},
    )
    return {
        "status": "success",
        "mensaje": f"Alerta #{alerta_id} cerrada exitosamente. Estado terminal: CERRADA.",
        "alerta": _alerta_out(repositories.get_alerta(alerta_id)),
    }


@router.post("/refuerzos/{refuerzo_id}/publicar", response_model=Dict[str, Any])
async def publicar_refuerzo(refuerzo_id: int, req: PublicarRefuerzoReq, docente: dict = Depends(get_current_docente)):
    """
    Registra la aprobación y publicación de un refuerzo (RN-17 / HU-05):
      - Exige req.confirmado == True (400 si es False).
      - Marca el refuerzo y la alerta como PUBLICADO y lo registra en auditoría.
    Nota: la creación automática de la actividad vía Web Services de Moodle aún no está implementada;
    el cmid devuelto es un identificador simulado y el docente crea la tarea desde el curso en Moodle.
    """
    if not req.confirmado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere confirmación explícita del docente antes de publicar en Moodle LMS (RN-17)."
        )

    refuerzo = repositories.get_refuerzo(refuerzo_id=refuerzo_id)
    if not refuerzo:
        raise HTTPException(status_code=404, detail="Refuerzo didáctico no encontrado.")
    alerta = _alerta_autorizada(refuerzo["alerta_id"], docente)

    simulated_cmid = 1000 + refuerzo_id
    cambios: Dict[str, Any] = {
        "estado": "PUBLICADO", "cmid": simulated_cmid, "fecha_publicacion": datetime.now(timezone.utc),
    }
    if req.titulo:
        cambios["titulo"] = req.titulo[:200]
    if req.instrucciones:
        cambios["instrucciones"] = req.instrucciones
    refuerzo = repositories.update_refuerzo(refuerzo_id, cambios)
    repositories.update_alerta(alerta["id"], {"estado": "PUBLICADO"})

    append_log(
        tipo_proceso="PUBLICAR_PUBLICADO",
        estado="EXITO",
        mensaje=f"Refuerzo #{refuerzo_id} aprobado y marcado como publicado (cmid simulado {simulated_cmid}).",
        detalle={"refuerzo_id": refuerzo_id, "cmid": simulated_cmid, "simulado": True,
                 "estudiante": alerta["nombres"], "curso": alerta["curso_codigo"]},
    )

    return {
        "status": "success",
        "mensaje": "Refuerzo aprobado. La creación automática en Moodle aún no está implementada (cmid simulado).",
        "cmid": simulated_cmid,
        "moodle_link": f"http://localhost:8080/course/view.php?id={alerta.get('curso_id') or ''}",
        "refuerzo": refuerzo,
    }


async def consultar_agente_ia(
    id_number: str,
    nombres: str,
    nota_final: float,
    notas_actividades: Dict[str, float],
    unidad_sugerida: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Conecta con el microservicio del agente IA (Ollama llama3.2:1b con respaldo heurístico).
    Aplica degradación controlada a plantilla si excede el límite de tiempo de 10s (RN-16).
    """
    payload = {
        "id_number": id_number,
        "nombres": nombres,
        "nota_final": nota_final,
        "notas_actividades": notas_actividades
    }

    try:
        async with httpx.AsyncClient(timeout=AGENT_TIMEOUT_SECONDS) as client:
            resp = await client.post(f"{AGENT_HOST}/api/v1/analyze", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                if "unidad_critica" in data and "diagnostico" in data:
                    return data
    except Exception:
        pass

    # Fallback determinista inmediato (RN-16 / HU-11B): el agente no respondió a tiempo
    unidad = unidad_sugerida or "la unidad con menor rendimiento"
    return {
        "unidad_critica": unidad,
        "diagnostico": (
            f"El estudiante {nombres} presenta dificultades en {unidad} (nota ponderada {nota_final:.2f}/10). "
            f"Se recomienda una guía didáctica práctica de recuperación."
        )[:250],
        "tipo_accion_sugerida": f"Refuerzo Didáctico Guiado ({unidad})",
        "fuente": "motor_heuristico_hu11b"
    }
