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
import re
import unicodedata
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("agent_service.planner")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
# Menor que el presupuesto del middleware para el chat (6 s): el agente siempre alcanza a responder (aunque sea sin
# plan) y el middleware cae a sus reglas sin que el docente espere de más.
INFERENCE_TIMEOUT = float(os.getenv("AGENT_PLAN_TIMEOUT_SECONDS", "5.0"))

# Saludos, cortesías y preguntas sobre el asistente: no requieren herramientas ni esperar a Ollama
_TRIVIAL = re.compile(r"^((hola|holi|hey|buenas|buenos dias|buen dia|buenas tardes|buenas noches|saludos) ?)?"
                      r"(como estas|como esta|como esta usted|como te va|como le va|que tal|que tal estas|"
                      r"gracias|muchas gracias|ok|okay|vale|listo|perfecto|chao|adios|hasta luego|ayuda|help|menu|"
                      r"opciones|quien eres|que eres|que puedes hacer|que sabes hacer|como funcionas|como funciona)?$")

def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto.lower()).strip()


def _nombre_materia(fullname: str) -> str:
    """'(SOF) PROGRAMACION ORIENTADA A OBJETOS - A' -> 'Programacion orientada a objetos (paralelo A)'."""
    nombre = re.sub(r"^\(\w+\)\s*", "", fullname or "").strip()
    paralelo = re.search(r"\s+-\s+([A-Z])$", nombre)
    if paralelo:
        nombre = nombre[:paralelo.start()]
    nombre = nombre.capitalize()
    return f"{nombre} (paralelo {paralelo.group(1)})" if paralelo else nombre


# Siglas institucionales de las materias -> sigla del código del curso (SOF-IS1-A, SOF-BDA-B...)
SIGLAS_MATERIAS = {"poo": "poo", "ed": "ed", "ma": "ma", "mcs": "mcs", "is1": "is1", "is": "is1", "isi": "is1",
                   "bda": "bda", "bd": "bda", "dw": "dw"}


def _curso_de(valor: str, cursos: List[Dict[str, Any]]) -> Optional[int]:
    """Id del curso si el valor nombra una materia (código, sigla o nombre); None si no."""
    texto = _normalizar(valor)
    if not texto:
        return None
    siglas_texto = {SIGLAS_MATERIAS[w] for w in re.findall(r"[a-z0-9]+", texto) if w in SIGLAS_MATERIAS}
    for c in cursos:
        partes = [p for p in _normalizar(c.get("shortname", "")).split("-") if p and p != "sof"]
        if partes and partes[0] in siglas_texto:
            return c["id"]
    for c in cursos:
        codigo = _normalizar(c.get("shortname", ""))
        siglas = [p for p in codigo.split("-") if len(p) > 1 and p != "sof"]
        palabras = re.findall(r"[a-z]{5,}", _normalizar(c.get("fullname", "")))
        if codigo and codigo in texto or any(re.search(rf"\b{re.escape(x)}\b", texto) for x in siglas[:1]):
            return c["id"]
        if palabras and sum(1 for p in palabras if p in texto) >= min(2, len(palabras)):
            return c["id"]
    return None


def limpiar_llamadas(llamadas: List[Dict[str, Any]], cursos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    El modelo 1B a veces pone el nombre de una materia como estudiante («Programación orientada a objetos»).
    Ese parámetro se descarta y, si falta, se usa como course_id: una materia nunca es un estudiante.
    """
    limpias = []
    for llamada in llamadas:
        params = dict(llamada.get("parametros") or {})
        for clave in ("estudiante", "student_query"):
            valor = params.get(clave)
            curso = _curso_de(str(valor), cursos) if isinstance(valor, str) else None
            if curso:
                params.pop(clave)
                params.setdefault("course_id", curso)
        if llamada.get("herramienta") == "proponer_refuerzo" and not params.get("student_query"):
            continue  # sin estudiante real no hay refuerzo que proponer
        limpias.append({**llamada, "parametros": params})
    return limpias


def _esquema_parametros(parametros: Dict[str, str]) -> Dict[str, Any]:
    props = {}
    for nombre, descripcion in parametros.items():
        tipo = ("integer" if descripcion.startswith("integer")
                else "number" if descripcion.startswith("number") else "string")
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


def es_trivial(mensaje: str) -> bool:
    texto = " ".join(re.findall(r"[a-z0-9]+", _normalizar(mensaje)))
    return bool(texto) and bool(_TRIVIAL.match(texto))


async def planificar(mensaje: str, herramientas: List[Dict[str, Any]], cursos: List[Dict[str, Any]],
                     course_id: Optional[int] = None) -> Dict[str, Any]:
    if es_trivial(mensaje):
        return {"llamadas": [], "fuente": "sin_plan_trivial"}
    contexto = "; ".join(f"{c['id']}={c['shortname']} {_nombre_materia(c.get('fullname', ''))}" for c in cursos)
    sistema = (
        "Asistente académico de EduMonitor AI. Elige herramientas y parámetros; no inventes datos. "
        "Todos los cursos o totales: sin course_id. Refuerzo: proponer_refuerzo(student_query). "
        "Un nombre de materia es un curso (course_id), nunca un estudiante. "
        "Nota con umbral (menor/mayor a X, entre X y Y): obtener_calificaciones(operador, umbral). "
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
            llamadas = limpiar_llamadas(llamadas, cursos)
            if llamadas:
                return {"llamadas": llamadas, "fuente": "ollama_slm"}
    except Exception as ex:  # timeout, Ollama caído o respuesta inválida
        logger.warning("Planificación con Ollama no disponible (%s).", ex.__class__.__name__)
    return {"llamadas": [], "fuente": "sin_plan_llm"}
