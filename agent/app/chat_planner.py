"""
Planificador de herramientas del agente (Fase A).

Recibe el mensaje del docente y el catálogo de herramientas del middleware, y pide a Ollama
(llama3.2:1b, *tool calling* vía /api/chat) qué herramientas invocar y con qué parámetros.
El agente NO ejecuta herramientas ni ve datos de estudiantes: sólo propone el plan; el middleware lo
valida (herramientas conocidas, cursos del docente) y ejecuta las consultas reales.
Si Ollama no responde dentro del timeout o no propone llamadas válidas, devuelve un plan vacío y el
middleware aplica su planificador determinista por reglas.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("agent_service.planner")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
# Menor que el timeout del middleware (10 s) para que el agente siempre alcance a responder (aunque sea sin plan)
INFERENCE_TIMEOUT = float(os.getenv("AGENT_PLAN_TIMEOUT_SECONDS", "8.0"))

def _esquema_parametros(parametros: Dict[str, str]) -> Dict[str, Any]:
    props = {}
    for nombre, descripcion in parametros.items():
        tipo = "integer" if descripcion.startswith("integer") else "string"
        props[nombre] = {"type": tipo}
    return {"type": "object", "properties": props, "required": []}


def _descripcion_corta(texto: str, limite: int = 110) -> str:
    """Primera frase de la descripción: el prompt corto mantiene la inferencia en CPU dentro del timeout."""
    frase = (texto or "").split(". ")[0].strip()
    return frase if len(frase) <= limite else frase[:limite].rsplit(" ", 1)[0]


def _herramientas_ollama(herramientas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{
        "type": "function",
        "function": {"name": h["nombre"], "description": _descripcion_corta(h.get("descripcion", "")),
                     "parameters": _esquema_parametros(h.get("parametros") or {})},
    } for h in herramientas]


async def planificar(mensaje: str, herramientas: List[Dict[str, Any]], cursos: List[Dict[str, Any]],
                     course_id: Optional[int] = None) -> Dict[str, Any]:
    contexto = ", ".join(f"{c['id']}={c['shortname']}" for c in cursos)
    sistema = (
        "Asistente académico de EduMonitor AI. Elige herramientas y parámetros; no inventes datos. "
        "Todos los cursos o totales: sin course_id. Refuerzo: proponer_refuerzo(student_query). "
        f"Cursos: {contexto or 'ninguno'}." + (f" Curso activo: {course_id}." if course_id else "")
    )
    try:
        async with httpx.AsyncClient(timeout=INFERENCE_TIMEOUT) as client:
            res = await client.post(f"{OLLAMA_HOST}/api/chat", json={
                "model": OLLAMA_MODEL, "stream": False,
                "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": mensaje}],
                "tools": _herramientas_ollama(herramientas),
                # num_predict acota la generación: el modelo 1B a veces no termina al usar herramientas y
                # bloquearía Ollama para las siguientes peticiones. num_ctx fijo evita recargar el modelo.
                "options": {"temperature": 0, "num_predict": 96, "num_ctx": 2048},
            })
        if res.status_code == 200:
            llamadas = []
            for call in (res.json().get("message") or {}).get("tool_calls") or []:
                funcion = call.get("function") or {}
                argumentos = funcion.get("arguments") or {}
                if isinstance(argumentos, str):
                    argumentos = json.loads(argumentos or "{}")
                llamadas.append({"herramienta": funcion.get("name"), "parametros": argumentos})
            if llamadas:
                return {"llamadas": llamadas, "fuente": "ollama_slm"}
    except Exception as ex:  # timeout, Ollama caído o respuesta inválida
        logger.warning("Planificación con Ollama no disponible (%s).", ex.__class__.__name__)
    return {"llamadas": [], "fuente": "sin_plan_llm"}
