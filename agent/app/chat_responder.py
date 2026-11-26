"""
Respuesta abierta con datos reales (RAG) para el chat de CoraIA.

El middleware consulta los datos REALES del docente (notas, alertas y actividades sincronizadas desde Moodle UTA)
y los envía como texto; Ollama sólo redacta la respuesta con esos datos. El prompt de sistema prohíbe inventar
cifras o estudiantes, y el middleware además verifica que cada cifra citada exista en los datos antes de mostrarla.
Si Ollama no responde dentro del timeout, se devuelve `respuesta: null` y el middleware pide precisar la consulta.
"""

import logging
import os
from typing import Any, Dict

import httpx

logger = logging.getLogger("agent_service.responder")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
# Menor que el presupuesto del middleware (AGENT_RAG_TIMEOUT_SECONDS = 28 s): el agente siempre alcanza a contestar
RAG_TIMEOUT = float(os.getenv("AGENT_RAG_TIMEOUT_SECONDS", "25.0"))
MAX_CONTEXTO = 5000

SISTEMA = {
    "es": (
        "Eres CoraIA, asistente académico de la UTA - FISEI. Responde a la pregunta del docente usando EXCLUSIVAMENTE "
        "los DATOS proporcionados (notas sobre 10 sincronizadas desde Moodle UTA).\n"
        "Reglas estrictas:\n"
        "1. No inventes estudiantes, notas, fechas, porcentajes ni cifras: copia los valores tal como aparecen en DATOS.\n"
        "2. Si los DATOS no contienen lo necesario (por ejemplo asistencia u horarios), responde sólo: "
        "\"No tengo ese dato en la información sincronizada de Moodle UTA.\"\n"
        "3. Empieza con una frase clave en **negritas** (estudiante destacado y su nota exacta /10, curso).\n"
        "4. Si mencionas varios estudiantes, usa viñetas '- ' ordenadas de menor a mayor nota, con nivel y tendencia.\n"
        "5. Máximo 8 líneas. Responde en español, con tono profesional y sin consejos ajenos al seguimiento académico."
    ),
    "en": (
        "You are CoraIA, the academic assistant of UTA - FISEI. Answer the teacher's question using ONLY the DATA "
        "provided (grades out of 10 synchronized from Moodle UTA; field labels are in Spanish).\n"
        "Strict rules:\n"
        "1. Never invent students, grades, dates, percentages or figures: copy values exactly as they appear in DATA.\n"
        "2. If DATA does not contain what is needed (e.g. attendance or schedules), answer only: "
        "\"I don't have that information in the data synchronized from Moodle UTA.\"\n"
        "3. Start with a key sentence in **bold** (highlighted student with exact grade /10, course).\n"
        "4. If you mention several students, use '- ' bullets ordered from lowest to highest grade, with level and trend.\n"
        "5. At most 8 lines. Answer in English, in a professional tone, with no advice unrelated to academic follow-up."
    ),
}


async def responder(pregunta: str, contexto: str, idioma: str = "es") -> Dict[str, Any]:
    """{'respuesta': texto | None, 'fuente': 'ollama_rag' | 'sin_respuesta_llm'}."""
    idioma = idioma if idioma in SISTEMA else "es"
    if not (pregunta or "").strip() or not (contexto or "").strip():
        return {"respuesta": None, "fuente": "sin_respuesta_llm"}
    usuario = f"DATOS:\n{contexto[:MAX_CONTEXTO]}\n\nPREGUNTA: {pregunta.strip()}"
    try:
        async with httpx.AsyncClient(timeout=RAG_TIMEOUT) as client:
            res = await client.post(f"{OLLAMA_HOST}/api/chat", json={
                "model": OLLAMA_MODEL, "stream": False,
                "messages": [{"role": "system", "content": SISTEMA[idioma]}, {"role": "user", "content": usuario}],
                # temperatura 0: respuesta reproducible y apegada a los datos; num_predict acota la longitud.
                # num_ctx igual al del planificador: Ollama no recarga el modelo entre peticiones.
                "options": {"temperature": 0, "num_predict": 180, "num_ctx": 2048},
            })
        if res.status_code == 200:
            texto = ((res.json().get("message") or {}).get("content") or "").strip()
            if texto:
                return {"respuesta": texto, "fuente": "ollama_rag"}
    except Exception as ex:  # timeout, Ollama caído o respuesta inválida
        logger.warning("Respuesta con datos no disponible (%s).", ex.__class__.__name__)
    return {"respuesta": None, "fuente": "sin_respuesta_llm"}
