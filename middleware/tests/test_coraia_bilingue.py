"""
CoraIA bilingüe (español / inglés), delimitación del dominio académico y trazabilidad de herramientas
(RF-09, RF-12 y Sección 7 de la especificación).
"""

import json

import pytest
from fastapi.testclient import TestClient

from app import repositories
from app.main import app
from app.services import agente_idioma
from app.services.agente_idioma import DOMINIO_EN, DOMINIO_ES

from test_agente_mejorado import _sin_llm
from test_fase_a import sincronizado  # noqa: F401 (fixture)

client = TestClient(app)


def _chat(headers, mensaje, **extra):
    res = client.post("/api/v1/agent/chat", headers=headers, json={"mensaje": mensaje, **extra})
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.parametrize("mensaje, idioma", [
    ("hello", "en"), ("Hi!", "en"), ("good morning", "en"), ("how are you?", "en"),
    ("how many students do I have in POO", "en"), ("who has the lowest grade", "en"), ("give me the PDF", "en"),
    ("hola", "es"), ("¿cuántos estudiantes tengo en POO?", "es"), ("dame el pdf", "es"), ("POO", "es"),
])
def test_deteccion_de_idioma(mensaje, idioma):
    assert agente_idioma.detectar_idioma(mensaje) == idioma


@pytest.mark.parametrize("mensaje, inicio", [
    ("hello", "Hello, Roberto! I'm CoraIA, the academic assistant of UTA - FISEI."),
    ("good morning", "Good morning, Roberto!"),
    ("how are you?", "I'm doing well, thank you, Roberto!"),
    ("thank you", "You're welcome, Roberto!"),
    ("bye", "Goodbye, Roberto!"),
])
def test_saludos_en_ingles(sincronizado, monkeypatch, mensaje, inicio):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, mensaje)
    assert data["respuesta"].startswith(inicio) and data["idioma"] == "en" and data["herramientas"] == []


def test_conteo_en_ingles_con_datos_reales(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "how many students do I have in POO")
    assert [(h["herramienta"], h["parametros"]) for h in data["herramientas"]] == [
        ("listar_estudiantes", {"course_id": 2, "solo_conteo": True})]
    assert data["respuesta"] == "In **Programación orientada a objetos — Section A** you have **4 students** enrolled."


def test_peor_nota_en_ingles(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "who has the lowest grade in POO?")
    assert data["herramientas"][0]["parametros"] == {"course_id": 2, "extremo": "peor"}
    assert data["respuesta"].startswith(
        "In **Programación orientada a objetos — Section A**, the student with the **lowest grade** is "
        "**Carlos Andrés Mendoza Paredes**, with **2.65/10** (critical).")


@pytest.mark.parametrize("mensaje, herramienta, inicio", [
    ("what is my name?", "perfil_docente", "You are **Roberto Patricio Gómez Salazar**"),
    ("full list of students in POO", "listar_estudiantes", "Students enrolled in **Programación orientada a objetos"),
    ("students at risk in POO", "identificar_alertas", "There "),
    ("grades of POO", "obtener_calificaciones", "In **Programación orientada a objetos — Section A** I reviewed"),
])
def test_consultas_en_ingles_responden_en_ingles(sincronizado, monkeypatch, mensaje, herramienta, inicio):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, mensaje)
    assert [h["herramienta"] for h in data["herramientas"]] == [herramienta]
    assert data["respuesta"].startswith(inicio) and data["idioma"] == "en"
    for espanol in ("Tiene ", "Hay ", "estudiantes matriculados", "Usted es", "revisé"):
        assert espanol not in data["respuesta"]


def test_plan_y_pdf_en_ingles_con_boton_de_descarga(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    plan = _chat(sincronizado, "Prepare a support plan for Carlos Mendoza")
    assert [h["herramienta"] for h in plan["herramientas"]] == ["proponer_refuerzo"]
    assert plan["respuesta"].startswith("I prepared a support plan for **Carlos Andrés Mendoza Paredes**")
    assert plan["herramientas"][0]["trazabilidad"]["parametros_validados"]["curso"] == "SOF-POO-A"   # curso resuelto
    data = _chat(sincronizado, "perfect, give me the PDF")
    assert [h["herramienta"] for h in data["herramientas"]] == ["generar_guia_pdf"]
    assert data["respuesta"].startswith("Done: I generated the **official UTA - FISEI reinforcement guide** for "
                                        "**Carlos Andrés Mendoza Paredes**")
    assert data["adjuntos"][0]["etiqueta"] == "Download PDF guide"
    assert client.get(data["adjuntos"][0]["url"], headers=sincronizado).content.startswith(b"%PDF-")


@pytest.mark.parametrize("mensaje, esperado", [
    ("2 + 2", DOMINIO_ES), ("¿cuánto es 15 * 3?", DOMINIO_ES), ("¿Cuál es la capital de España?", DOMINIO_ES),
    ("cuéntame un chiste", DOMINIO_ES), ("what is the capital of Spain?", DOMINIO_EN), ("tell me a joke", DOMINIO_EN),
    ("what is 5 * 3", DOMINIO_EN), ("what's the weather like today?", DOMINIO_EN),
])
def test_fuera_del_dominio_academico_delimita_su_alcance(sincronizado, monkeypatch, mensaje, esperado):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, mensaje)
    assert data["respuesta"] == esperado and data["plan_fuente"] == "fuera_de_dominio" and data["herramientas"] == []
    assert "No estoy seguro" not in data["respuesta"] and "10" not in data["respuesta"]


def test_una_consulta_academica_con_numeros_no_se_confunde_con_un_calculo(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "estudiantes con nota entre 6 y 7")
    assert [h["herramienta"] for h in data["herramientas"]] == ["obtener_calificaciones"]


def test_espanol_sin_plurales_mecanicos(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "¿Qué estudiantes de POO necesitan atención?")
    assert data["idioma"] == "es"
    assert "(s)" not in data["respuesta"] and "(n)" not in data["respuesta"]
    assert data["respuesta"].startswith("Hay **")


def test_trazabilidad_de_herramientas_y_parametros_validados(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "notas de POO")
    traza = data["herramientas"][0]["trazabilidad"]
    assert traza["herramienta"] == "obtener_calificaciones"
    assert traza["parametros_validados"]["curso"] == "SOF-POO-A"           # el código del curso, no su id interno
    assert isinstance(traza["parametros_validados"]["docente_id"], int)
    assert traza["estado"] == "OK" and traza["resultado"] == "4 registros"
    assert traza["fuente"].startswith("Sincronizado desde Moodle UTA · ")
    # RF-12: queda registrada en la auditoría, sin tokens ni contraseñas
    log = next(x for x in reversed(repositories.filas("logs_sistema")) if x["tipo_proceso"] == "AGENTE_HERRAMIENTA")
    assert log["detalle"]["trazabilidad"] == traza
    crudo = json.dumps(log["detalle"]).lower()
    assert "token" not in crudo and "password" not in crudo and "contrase" not in crudo


def test_trazabilidad_de_un_error_y_de_un_alcance_global(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "dame el pdf de U-99")
    traza = data["herramientas"][0]["trazabilidad"]
    assert traza["estado"] == "ERROR" and "U-99" in traza["resultado"]
    data = _chat(sincronizado, "reprobados en todos mis cursos")
    traza = data["herramientas"][0]["trazabilidad"]
    assert traza["parametros_validados"]["curso"] == "todos los cursos del docente"
    assert traza["parametros_validados"]["operador"] == "<"


def test_fecha_de_entrega_del_refuerzo_en_hora_de_ecuador():
    from datetime import datetime
    from app.services.agente_herramientas import hora_ecuador
    assert hora_ecuador("2026-11-22T04:59:00") == datetime(2026, 11, 21, 23, 59)          # UTC sin zona
    assert hora_ecuador("2026-11-21T23:59:00-05:00") == datetime(2026, 11, 21, 23, 59)    # ya en hora local


def test_ficha_de_estudiante_ordenada_sin_codigo_interno(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "Dame las notas de Carlos Mendoza")
    texto = data["respuesta"]
    assert "**Carlos Andrés Mendoza Paredes** (C.I. 1804923199) · " in texto
    assert "(U-04)" not in texto and "SOF-POO-A" not in texto
    assert "**Programación orientada a objetos — Paralelo A**" in texto
    assert "Promedio: **" in texto and "Exámenes: " in texto and "| Tareas: " in texto and "| APE: " in texto
    assert "Tendencia: " in texto
    assert texto.count("pendiente de calificación") <= 1          # las pendientes se agrupan en un conteo


def test_ficha_de_estudiante_en_ingles(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    texto = _chat(sincronizado, "grades of Carlos Mendoza")["respuesta"]
    assert "**Carlos Andrés Mendoza Paredes** (ID 1804923199) · " in texto and "(U-04)" not in texto
    assert "Average: **" in texto and "Exams: " in texto and "| Assignments: " in texto and "Trend: " in texto


def test_resumen_de_incidencias_agrupa_las_pendientes():
    textos = {"SIN_ENTREGA": "sin entrega", "NOTA_0": "nota 0"}
    pend = ("actividad pendiente de calificación", "actividades pendientes de calificación")
    incid = ["U1-T2 NOTA_0", "U2-T4 SIN_ENTREGA"] + [f"U3-T{i} PENDIENTE" for i in range(1, 6)]
    assert agente_idioma.resumen_incidencias(incid, textos, pend) == (
        "U1-T2 (nota 0), U2-T4 (sin entrega) · 5 actividades pendientes de calificación")
    assert agente_idioma.resumen_incidencias(["U3-T1 PENDIENTE"], textos, pend) == "1 actividad pendiente de calificación"


def test_cada_alerta_indica_su_parcial(sincronizado):  # noqa: F811
    alertas = client.get("/api/v1/alertas", headers=sincronizado).json()
    assert alertas and all(a["parcial"] in (1, 2) for a in alertas)


def test_alerta_publicada_enlaza_su_tarea_en_moodle():
    from app.config import settings
    from app.routers.alerts import _alerta_out
    base = {"id": 1, "curso_id": 2, "curso_codigo": "SOF-POO-A", "curso_nombre": "POO", "id_number": "U-04",
            "nombres": "Carlos", "email": "c@uta.edu.ec", "regla": "R1_NOTA_CRITICA", "nivel": "CRITICO",
            "nota_final": 3.4, "motivo": "Nota crítica", "numero_parcial": 1, "refuerzo_cmid": 165}
    publicada = _alerta_out({**base, "estado": "PUBLICADO"})
    assert publicada["moodle_url"] == f"{settings.MOODLE_EXTERNAL_URL}/mod/assign/view.php?id=165"
    assert _alerta_out({**base, "estado": "ABIERTA"})["moodle_url"] is None
    assert _alerta_out({**base, "estado": "PUBLICADO", "refuerzo_cmid": None})["moodle_url"] is None
