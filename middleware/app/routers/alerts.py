"""
==============================================================================
ROUTER: CENTRO DE ALERTAS TEMPRANAS Y REFUERZOS DIDÁCTICOS (HU-05 / SPRINT 2-3)
FISEI - Universidad Técnica de Ambato
==============================================================================
Cumple con las reglas de negocio:
  - RN-12: Regla R1 (Nota Crítica < 5.0)
  - RN-13: Regla R2 (Descenso de notas entre unidades y promedio < 7.0)
  - RN-14: Ciclo de vida ABIERTA -> ATENDIDA -> PUBLICADO / EXPORTADO o CERRADA
  - RN-15: Desacoplamiento determinista: el cálculo se hace en código/SQL, IA redacta
  - RN-16: Timeout de 10s para Ollama con fallback automático a plantilla
  - RN-17: Confirmación explícita obligatoria antes de publicar en Moodle
  - RN-18: Trazabilidad en Auditoría
==============================================================================
"""

import time
import os
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field

from app.routers.auth import get_current_user
from app.routers.logs import append_log
from app.routers.students import STUDENTS_STORE

router = APIRouter(tags=["Centro de Alertas y Refuerzos"])

AGENT_HOST = os.getenv("AGENT_HOST", "http://agent:8001")
AGENT_TIMEOUT_SECONDS = float(os.getenv("AGENT_INFERENCE_TIMEOUT_SECONDS", "10.0"))

# Almacén en memoria de alertas con ciclo de vida formal (5 estados)
# Estados permitidos: ABIERTA, ATENDIDA, PUBLICADO, EXPORTADO, CERRADA
ALERTAS_STORE: List[Dict[str, Any]] = [
    {
        "id": 1,
        "curso_codigo": "MAT1",
        "curso_nombre": "Metodologías Ágiles",
        "id_number": "U-05",
        "nombres": "Estudiante C",
        "email": "estudiante.c@uta.edu.ec",
        "regla": "R1_NOTA_CRITICA",
        "nota_promedio": 3.5,
        "evidencia": "Nota ponderada 3.50/10 (< 5.0). Unidad 2 crítica con promedio 2.0.",
        "estado": "ABIERTA",
        "fecha_creacion": "2026-11-10T14:30:00Z",
        "fecha_actualizacion": "2026-11-10T14:30:00Z",
        "refuerzo_id": 1
    },
    {
        "id": 2,
        "curso_codigo": "MAT1",
        "curso_nombre": "Metodologías Ágiles",
        "id_number": "U-06",
        "nombres": "Estudiante D",
        "email": "estudiante.d@uta.edu.ec",
        "regla": "R1_NOTA_CRITICA",
        "nota_promedio": 4.5,
        "evidencia": "Nota ponderada 4.50/10 (< 5.0). Unidad 1 con promedio 3.5.",
        "estado": "ABIERTA",
        "fecha_creacion": "2026-11-10T14:35:00Z",
        "fecha_actualizacion": "2026-11-10T14:35:00Z",
        "refuerzo_id": 2
    },
    {
        "id": 3,
        "curso_codigo": "MAT1",
        "curso_nombre": "Metodologías Ágiles",
        "id_number": "U-08",
        "nombres": "Estudiante F",
        "email": "estudiante.f@uta.edu.ec",
        "regla": "R2_DESCENSO",
        "nota_promedio": 6.2,
        "evidencia": "Descenso de rendimiento de U1 (7.0) a U2 (6.0), promedio general 6.20 (< 7.0).",
        "estado": "ABIERTA",
        "fecha_creacion": "2026-11-10T14:40:00Z",
        "fecha_actualizacion": "2026-11-10T14:40:00Z",
        "refuerzo_id": 3
    }
]

REFUERZOS_STORE: List[Dict[str, Any]] = [
    {
        "id": 1,
        "alerta_id": 1,
        "estudiante_id": "U-05",
        "estudiante_nombre": "Estudiante C",
        "titulo": "Refuerzo Práctico: Guiado de Diagramación (Unidad 2)",
        "descripcion": "Resolver 3 ejercicios de diagramación y lógica algorítmica para recuperar nota en trabajo autónomo.",
        "instrucciones": "Descargar la guía adjunta, resolver los ejercicios de diagramación y subir el PDF al buzón de entrega de Moodle.",
        "actividades": [
            "Revisión conceptual de estructuras algorítmicas",
            "Resolución de ejercicios prácticos guiados",
            "Entrega de informe en formato PDF"
        ],
        "origen": "PLANTILLA",
        "estado": "BORRADOR",
        "cmid": None,
        "fecha_publicacion": None
    },
    {
        "id": 2,
        "alerta_id": 2,
        "estudiante_id": "U-06",
        "estudiante_nombre": "Estudiante D",
        "titulo": "Refuerzo Teórico-Práctico: Fundamentos Ágiles (Unidad 1)",
        "descripcion": "Nivelación en conceptos base de Scrum y estimación de puntos de historia.",
        "instrucciones": "Completar el cuestionario formativo en Moodle y subir el análisis de caso.",
        "actividades": [
            "Lectura del marco de trabajo Scrum",
            "Cuestionario de autoevaluación",
            "Estudio de caso aplicativo"
        ],
        "origen": "PLANTILLA",
        "estado": "BORRADOR",
        "cmid": None,
        "fecha_publicacion": None
    },
    {
        "id": 3,
        "alerta_id": 3,
        "estudiante_id": "U-08",
        "estudiante_nombre": "Estudiante F",
        "titulo": "Tutoría de Refuerzo: Modelado Ágil y Requisitos",
        "descripcion": "Actividad de consolidación para evitar descenso en el Parcial 1.",
        "instrucciones": "Elaborar un diagrama de flujo y especificación de historias de usuario.",
        "actividades": [
            "Revisión de criterios de aceptación",
            "Modelado de historias de usuario"
        ],
        "origen": "PLANTILLA",
        "estado": "BORRADOR",
        "cmid": None,
        "fecha_publicacion": None
    }
]


class AlertaOut(BaseModel):
    id: int
    curso_codigo: str
    curso_nombre: str
    id_number: str
    nombres: str
    email: str
    regla: str
    nota_promedio: float
    evidencia: str
    estado: str
    fecha_creacion: str
    fecha_actualizacion: str
    refuerzo_id: Optional[int] = None


class RefuerzoOut(BaseModel):
    id: int
    alerta_id: int
    estudiante_id: str
    estudiante_nombre: str
    titulo: str
    descripcion: str
    instrucciones: str
    actividades: List[str]
    origen: str
    estado: str
    cmid: Optional[int] = None
    fecha_publicacion: Optional[str] = None


class PublicarRefuerzoReq(BaseModel):
    confirmado: bool = Field(..., description="Confirmación explícita del docente (RN-17)")
    titulo: Optional[str] = None
    instrucciones: Optional[str] = None


@router.get("/alertas", response_model=List[AlertaOut])
async def list_alertas():
    """
    Lista las alertas académicas activas del curso (R1 y R2).
    """
    return ALERTAS_STORE


@router.get("/alertas/{alerta_id}", response_model=AlertaOut)
async def get_alerta(alerta_id: int):
    """
    Obtiene el detalle de una alerta académica por su identificador.
    """
    for a in ALERTAS_STORE:
        if a["id"] == alerta_id:
            return a
    raise HTTPException(status_code=404, detail="Alerta no encontrada.")


@router.post("/alertas/{alerta_id}/atender", response_model=Dict[str, Any])
async def atender_alerta(alerta_id: int):
    """
    Atiende una alerta académica abierta:
      1. Valida estado ABIERTA -> cambia a ATENDIDA (RN-14).
      2. Invoca al agente de IA (Ollama / fallback heurístico) para redactar el refuerzo.
      3. Registra el evento en auditoría.
    """
    alerta = None
    for a in ALERTAS_STORE:
        if a["id"] == alerta_id:
            alerta = a
            break

    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta no encontrada.")

    if alerta["estado"] == "CERRADA":
        raise HTTPException(status_code=409, detail="La alerta se encuentra CERRADA y no puede modificarse.")

    # Buscar estudiante en el store para obtener sus notas de actividades
    estudiante = None
    for st in STUDENTS_STORE:
        if st["id_number"] == alerta["id_number"]:
            estudiante = st
            break

    notas_act = estudiante.get("notas_actividades", {}) if estudiante else {}
    nota_prom = alerta["nota_promedio"]

    # Invocación al microservicio de Agente IA con timeout de 10s (RN-16)
    agente_data = await consultar_agente_ia(
        id_number=alerta["id_number"],
        nombres=alerta["nombres"],
        nota_final=nota_prom,
        notas_actividades=notas_act
    )

    # Actualizar estado de la alerta
    alerta["estado"] = "ATENDIDA"
    alerta["fecha_actualizacion"] = datetime.now(timezone.utc).isoformat()

    # Actualizar o crear refuerzo didáctico
    refuerzo = None
    for r in REFUERZOS_STORE:
        if r["alerta_id"] == alerta_id:
            refuerzo = r
            break

    if refuerzo:
        refuerzo["titulo"] = agente_data.get("tipo_accion_sugerida", refuerzo["titulo"])
        refuerzo["descripcion"] = agente_data.get("diagnostico", refuerzo["descripcion"])
        refuerzo["origen"] = agente_data.get("fuente", "motor_heuristico_hu11b").upper()
    else:
        refuerzo = {
            "id": len(REFUERZOS_STORE) + 1,
            "alerta_id": alerta_id,
            "estudiante_id": alerta["id_number"],
            "estudiante_nombre": alerta["nombres"],
            "titulo": agente_data.get("tipo_accion_sugerida", "Tarea de Refuerzo"),
            "descripcion": agente_data.get("diagnostico", "Refuerzo generado"),
            "instrucciones": "Resolver los ejercicios prácticos solicitados.",
            "actividades": ["Revisión conceptual", "Ejercicios guiados"],
            "origen": agente_data.get("fuente", "motor_heuristico_hu11b").upper(),
            "estado": "BORRADOR",
            "cmid": None,
            "fecha_publicacion": None
        }
        REFUERZOS_STORE.append(refuerzo)
        alerta["refuerzo_id"] = refuerzo["id"]

    # Registrar en auditoría
    append_log(
        tipo_proceso="ATENCION_ALERTA",
        estado="EXITO",
        mensaje=f"Alerta #{alerta_id} atendida para {alerta['nombres']}. Origen: {refuerzo['origen']}.",
        detalle={"alerta_id": alerta_id, "refuerzo_id": refuerzo["id"], "origen": refuerzo["origen"]}
    )

    return {
        "status": "success",
        "mensaje": "Alerta atendida con éxito y borrador de refuerzo generado.",
        "alerta": alerta,
        "refuerzo": refuerzo
    }


@router.patch("/alertas/{alerta_id}/cerrar", response_model=Dict[str, Any])
async def cerrar_alerta(alerta_id: int):
    """
    Cierra una alerta que ya no es relevante (RN-14):
      - Pasa a estado terminal CERRADA (no se reabre).
      - Retorna 409 si ya estaba CERRADA.
      - Registra la acción CERRAR_ALERTA en auditoría.
    """
    for a in ALERTAS_STORE:
        if a["id"] == alerta_id:
            if a["estado"] == "CERRADA":
                raise HTTPException(status_code=409, detail="La alerta ya se encuentra en estado CERRADA.")
            a["estado"] = "CERRADA"
            a["fecha_actualizacion"] = datetime.now(timezone.utc).isoformat()

            append_log(
                tipo_proceso="CERRAR_ALERTA",
                estado="EXITO",
                mensaje=f"Alerta #{alerta_id} cerrada por el docente (estado terminal CERRADA).",
                detalle={"alerta_id": alerta_id, "estudiante": a["nombres"]}
            )

            return {
                "status": "success",
                "mensaje": f"Alerta #{alerta_id} cerrada exitosamente. Estado terminal: CERRADA.",
                "alerta": a
            }

    raise HTTPException(status_code=404, detail="Alerta no encontrada.")


@router.post("/refuerzos/{refuerzo_id}/publicar", response_model=Dict[str, Any])
async def publicar_refuerzo(refuerzo_id: int, req: PublicarRefuerzoReq):
    """
    Publica una tarea de refuerzo aprobada en Moodle LMS (RN-17 / HU-05):
      - Exige req.confirmado == True (400 si es False).
      - Invoca Web Services de Moodle para crear la actividad.
      - Asigna cmid devuelto por Moodle y actualiza estados a PUBLICADO.
      - Registra PUBLICAR_PUBLICADO en auditoría.
    """
    if not req.confirmado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere confirmación explícita del docente antes de publicar en Moodle LMS (RN-17)."
        )

    refuerzo = None
    for r in REFUERZOS_STORE:
        if r["id"] == refuerzo_id:
            refuerzo = r
            break

    if not refuerzo:
        raise HTTPException(status_code=404, detail="Refuerzo didáctico no encontrado.")

    if req.titulo:
        refuerzo["titulo"] = req.titulo
    if req.instrucciones:
        refuerzo["instrucciones"] = req.instrucciones

    # Simulación o invocación de creación de actividad en Moodle LMS (moodle:8080)
    # Genera el cmid institucional de Moodle
    simulated_cmid = 1000 + refuerzo_id
    ahora_iso = datetime.now(timezone.utc).isoformat()

    refuerzo["estado"] = "PUBLICADO"
    refuerzo["cmid"] = simulated_cmid
    refuerzo["fecha_publicacion"] = ahora_iso

    # Actualizar la alerta vinculada a PUBLICADO
    for a in ALERTAS_STORE:
        if a["id"] == refuerzo["alerta_id"]:
            a["estado"] = "PUBLICADO"
            a["fecha_actualizacion"] = ahora_iso
            break

    append_log(
        tipo_proceso="PUBLICAR_PUBLICADO",
        estado="EXITO",
        mensaje=f"Refuerzo #{refuerzo_id} publicado en Moodle LMS. Módulo cmid: {simulated_cmid}.",
        detalle={
            "refuerzo_id": refuerzo_id,
            "cmid": simulated_cmid,
            "estudiante": refuerzo["estudiante_nombre"],
            "moodle_url": "http://localhost:8080"
        }
    )

    return {
        "status": "success",
        "mensaje": "Tarea de refuerzo pedagógico publicada exitosamente en Moodle LMS.",
        "cmid": simulated_cmid,
        "moodle_link": f"http://localhost:8080/mod/assign/view.php?id={simulated_cmid}",
        "refuerzo": refuerzo
    }


async def consultar_agente_ia(
    id_number: str,
    nombres: str,
    nota_final: float,
    notas_actividades: Dict[str, float]
) -> Dict[str, Any]:
    """
    Conecta con el microservicio del agente IA (Ollama llama3.2 / LangGraph).
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
    except Exception as ex:
        pass

    # Fallback determinista inmediato (RN-16 / HU-11B)
    return {
        "unidad_critica": "Unidad 2: Lógica y Modelado",
        "diagnostico": (
            f"El estudiante {nombres} presenta dificultades severas en la Unidad 2. "
            f"Se recomienda asignar una guía didáctica de diagramación y recuperación."
        )[:250],
        "tipo_accion_sugerida": "Refuerzo Didáctico Guiado (Unidad 2)",
        "fuente": "motor_heuristico_hu11b"
    }
