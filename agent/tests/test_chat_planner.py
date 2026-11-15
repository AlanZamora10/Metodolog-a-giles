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


CURSOS_UTA = CURSOS + [{"id": 3, "shortname": "SOF-ED-B", "fullname": "(SOF) ESTRUCTURA DE DATOS - B"}]


def test_materia_como_estudiante_se_convierte_en_curso():
    llamadas = chat_planner.limpiar_llamadas([
        {"herramienta": "obtener_calificaciones", "parametros": {"estudiante": "Programación orientada a objetos"}},
        {"herramienta": "obtener_calificaciones", "parametros": {"estudiante": "Estructura de datos", "course_id": 2}},
        {"herramienta": "obtener_calificaciones", "parametros": {"estudiante": "Carlos Mendoza"}},
        {"herramienta": "proponer_refuerzo", "parametros": {"student_query": "POO"}},
    ], CURSOS_UTA)
    assert llamadas == [
        {"herramienta": "obtener_calificaciones", "parametros": {"course_id": 2}},
        {"herramienta": "obtener_calificaciones", "parametros": {"course_id": 2}},   # course_id explícito se respeta
        {"herramienta": "obtener_calificaciones", "parametros": {"estudiante": "Carlos Mendoza"}},
    ]


def test_el_prompt_incluye_el_nombre_de_la_materia_y_la_regla(monkeypatch):
    capturado = {}

    def handler(request):
        capturado["json"] = request.read().decode("utf-8")
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "obtener_calificaciones",
                          "arguments": {"estudiante": "Programacion orientada a objetos"}}}]}})

    real = httpx.AsyncClient
    monkeypatch.setattr(chat_planner.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    herramientas = HERRAMIENTAS + [{"nombre": "obtener_calificaciones", "descripcion": "Notas",
                                    "parametros": {"estudiante": "string", "umbral": "number (opcional)"}}]
    plan = asyncio.run(chat_planner.planificar("notas de programación orientada a objetos", herramientas, CURSOS_UTA))
    assert plan["llamadas"] == [{"herramienta": "obtener_calificaciones", "parametros": {"course_id": 2}}]
    assert "Programacion orientada a objetos (paralelo A)" in capturado["json"]
    assert "nunca un estudiante" in capturado["json"]
    assert '"umbral":{"type":"number"}' in capturado["json"].replace(" ", "")
