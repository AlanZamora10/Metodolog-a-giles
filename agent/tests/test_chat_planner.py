"""Planificador de herramientas del agente (Fase A): Ollama tool calling con respaldo sin plan."""

import asyncio

import httpx

from app import chat_planner

HERRAMIENTAS = [
    {"nombre": "identificar_alertas", "descripcion": "Alertas R1/R2",
     "parametros": {"course_id": "integer (opcional)", "regla": "R1 | R2 (opcional)"}},
    {"nombre": "listar_cursos_autorizados", "descripcion": "Cursos del docente", "parametros": {}},
]
CURSOS = [{"id": 2, "shortname": "SOF-POO-A", "fullname": "(SOF) PROGRAMACION ORIENTADA A OBJETOS - A"}]


def test_sin_ollama_devuelve_plan_vacio(monkeypatch):
    monkeypatch.setattr(chat_planner, "OLLAMA_HOST", "http://127.0.0.1:9")
    monkeypatch.setattr(chat_planner, "INFERENCE_TIMEOUT", 1.0)
    plan = asyncio.run(chat_planner.planificar("alertas de POO", HERRAMIENTAS, CURSOS))
    assert plan == {"llamadas": [], "fuente": "sin_plan_llm"}


def test_convierte_tool_calls_de_ollama(monkeypatch):
    capturado = {}

    def handler(request):
        capturado["json"] = request.read().decode()
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "identificar_alertas", "arguments": {"course_id": 2, "regla": "R1"}}}]}})

    real = httpx.AsyncClient
    monkeypatch.setattr(chat_planner.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    plan = asyncio.run(chat_planner.planificar("críticos de POO", HERRAMIENTAS, CURSOS))
    assert plan == {"fuente": "ollama_slm",
                    "llamadas": [{"herramienta": "identificar_alertas", "parametros": {"course_id": 2, "regla": "R1"}}]}
    assert '"tools"' in capturado["json"] and "SOF-POO-A" in capturado["json"]
