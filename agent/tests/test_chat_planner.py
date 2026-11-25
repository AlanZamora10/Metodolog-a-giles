"""Planificador de herramientas del agente (Fase A): Ollama tool calling con respaldo sin plan."""

import asyncio
import json

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
    assert "Asistente académico CoraIA (UTA - FISEI)" in json.loads(capturado["json"])["messages"][0]["content"]
    assert "EduMonitor" not in capturado["json"]                      # la marca visible es CoraIA
    assert "Temas ajenos al seguimiento académico" in json.loads(capturado["json"])["messages"][0]["content"]


def test_mensajes_triviales_no_esperan_a_ollama(monkeypatch):
    def no_llamar(**kw):
        raise AssertionError("un saludo no debe consultar a Ollama")

    monkeypatch.setattr(chat_planner.httpx, "AsyncClient", no_llamar)
    for mensaje in ("Hola", "¡Buenos días!", "gracias", "¿Qué puedes hacer?", "ayuda", "¿Quién eres?",
                    "¿Cómo estás?", "Hola, ¿cómo te va?", "Buenas tardes, ¿cómo está usted?", "¿Qué tal?"):
        assert asyncio.run(chat_planner.planificar(mensaje, HERRAMIENTAS, CURSOS)) == {
            "llamadas": [], "fuente": "sin_plan_trivial"}
    assert chat_planner.INFERENCE_TIMEOUT <= 5


def test_respuesta_sin_llamadas_estructuradas_devuelve_plan_vacio(monkeypatch):
    real = httpx.AsyncClient
    monkeypatch.setattr(chat_planner.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"message": {"role": "assistant", "content": "No sé qué hacer"}})), **kw))
    plan = asyncio.run(chat_planner.planificar("cómo van mis cursos", HERRAMIENTAS, CURSOS))
    assert plan == {"llamadas": [], "fuente": "sin_plan_llm"}


def test_una_consulta_real_no_es_trivial():
    for mensaje in ("hola, ¿cómo van mis cursos?", "notas de Carlos", "", "¿qué tal va POO?"):
        assert not chat_planner.es_trivial(mensaje), mensaje


def test_siglas_institucionales_se_convierten_en_curso():
    cursos = [{"id": 5, "shortname": "SOF-IS1-A", "fullname": "(SOF) INGENIERIA DE SOFTWARE I - A"},
              {"id": 6, "shortname": "SOF-BDA-B", "fullname": "(SOF) BASES DE DATOS AVANZADAS - B"},
              {"id": 7, "shortname": "SOF-DW-A", "fullname": "(SOF) DESARROLLO WEB - A"}]
    llamadas = chat_planner.limpiar_llamadas([
        {"herramienta": "obtener_calificaciones", "parametros": {"estudiante": "IS"}},
        {"herramienta": "obtener_calificaciones", "parametros": {"estudiante": "bd"}},
        {"herramienta": "obtener_calificaciones", "parametros": {"estudiante": "dw"}},
    ], cursos)
    assert [ll["parametros"] for ll in llamadas] == [{"course_id": 5}, {"course_id": 6}, {"course_id": 7}]


def test_guia_pdf_sin_estudiante_se_descarta_y_con_estudiante_se_conserva():
    llamadas = chat_planner.limpiar_llamadas([
        {"herramienta": "generar_guia_pdf", "parametros": {}},
        {"herramienta": "generar_guia_pdf", "parametros": {"student_query": "POO"}},          # una materia no es un estudiante
        {"herramienta": "generar_guia_pdf", "parametros": {"student_query": "Fernanda Altamirano"}},
    ], CURSOS_UTA)
    assert llamadas == [{"herramienta": "generar_guia_pdf", "parametros": {"student_query": "Fernanda Altamirano"}}]
