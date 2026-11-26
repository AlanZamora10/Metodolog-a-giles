"""
NLU flexible de CoraIA: sinónimos, abreviaturas, preguntas abiertas, desambiguación de materia, respuesta con datos
reales (LLM restringido a los datos) y filtro estricto fuera del dominio académico.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import agente_herramientas, agente_nlu, sync_service
from app.services.agente_idioma import DOMINIO_ES

from test_agente_mejorado import _sin_llm
from test_fase_a import sincronizado  # noqa: F401 (fixture)

client = TestClient(app)
POO = "Programación orientada a objetos — Paralelo A"


def _chat(headers, mensaje, **extra):
    res = client.post("/api/v1/agent/chat", headers=headers, json={"mensaje": mensaje, **extra})
    assert res.status_code == 200, res.text
    return res.json()


def _plan(data):
    return [(h["herramienta"], h["parametros"]) for h in data["herramientas"]]


# ------------------------------------------------------------------ normalización canónica
@pytest.mark.parametrize("texto, esperado", [
    ("cual es el alumno mas bajo de promedio en poo", "cual es el estudiante con la peor nota en poo"),
    ("quien va ganando la materia", "el estudiante con la mejor nota"),
    ("cual es el menor promedio", "cual es la peor nota"),
    ("cuantos alumnos jalaron", "cuantos estudiantes reprobados"),
    ("cuantos aprobaron", "cuantos aprobados"),
    ("notas de base de datos", "notas de bda"),
    ("la alumna mas destacada", "el estudiante con la mejor nota"),
])
def test_canonizacion_de_sinonimos_y_coloquialismos(texto, esperado):
    assert agente_nlu.canonizar(texto) == esperado


@pytest.mark.parametrize("texto, orden", [
    ("dame el ranking de notas", "desc"), ("ordenalos de menor a mayor", "asc"),
    ("tabla de posiciones de poo", "desc"), ("notas de poo", None),
])
def test_ranking(texto, orden):
    assert agente_nlu.orden_ranking(texto) == orden


def test_coincidencia_parcial_de_materias():
    cursos = [{"id": 1, "fullname": "(SOF) BASES DE DATOS AVANZADAS - B"},
              {"id": 2, "fullname": "(SOF) PROGRAMACION ORIENTADA A OBJETOS - A"},
              {"id": 3, "fullname": "(SOF) ESTRUCTURA DE DATOS - B"}]
    norm = agente_herramientas._normalizar
    assert [c["id"] for c in agente_nlu.cursos_por_nombre("notas de programacion", cursos, norm)] == [2]
    assert [c["id"] for c in agente_nlu.cursos_por_nombre("las estructuras", cursos, norm)] == [3]
    assert agente_nlu.cursos_por_nombre("los datos del curso", cursos, norm) == []     # «datos» es ambiguo


# ------------------------------------------------------------------ preguntas abiertas resueltas por reglas
def test_alumno_mas_bajo_de_promedio_en_poo(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "¿cuál es el alumno más bajo de promedio en POO?")
    assert _plan(data) == [("obtener_calificaciones", {"course_id": 2, "extremo": "peor"})]
    assert data["respuesta"].startswith(f"En **{POO}**, el estudiante con la **menor calificación** es "
                                        "**Carlos Andrés Mendoza Paredes**, con **2.65/10** (crítico).")
    assert "No estoy seguro" not in data["respuesta"]


def test_quien_va_ganando_usa_el_curso_activo(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "¿quién va ganando la materia?", course_id=2)
    assert _plan(data) == [("obtener_calificaciones", {"course_id": 2, "extremo": "mejor"})]
    assert data["respuesta"].startswith(f"En **{POO}**, el estudiante con la **mayor calificación** es")


def test_ranking_de_notas_en_tabla_ordenada(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "dame el ranking de notas", course_id=2)
    assert _plan(data) == [("obtener_calificaciones", {"course_id": 2, "ranking": "desc"})]
    notas = [f["nota_final"] for f in data["herramientas"][0]["resultado"]["calificaciones"]]
    assert notas == sorted(notas, reverse=True)
    assert data["respuesta"].startswith(f"**Ranking de notas** en **{POO}** (de mayor a menor promedio): lidera ")
    assert "| # | Estudiante | Promedio | Estado / Tendencia |" in data["respuesta"]
    assert data["herramientas"][0]["trazabilidad"]["parametros_validados"]["ranking"] == "desc"


@pytest.mark.parametrize("mensaje, criterio", [
    ("¿cuántos aprobaron?", {"operador": ">=", "umbral": 7.0}),
    ("¿quiénes van jalando en POO?", {"operador": "<", "umbral": 7.0}),
])
def test_aprobados_y_reprobados_coloquiales(sincronizado, monkeypatch, mensaje, criterio):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, mensaje, course_id=2)
    nombre, params = _plan(data)[0]
    assert nombre == "obtener_calificaciones" and {k: params[k] for k in criterio} == criterio


def test_tareas_que_faltan_por_calificar(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "¿qué tareas faltan por calificar?", course_id=2)
    assert _plan(data) == [("analizar_actividades", {"course_id": 2, "solo_pendientes": True})]
    acts = data["herramientas"][0]["resultado"]["actividades"]
    assert acts and all(a["pendientes"] > 0 for a in acts)
    assert data["respuesta"].startswith("Tiene **") and "por calificar** en **" in data["respuesta"]
    assert "| Actividad | Nombre | Por calificar |" in data["respuesta"]


@pytest.mark.parametrize("mensaje", ["¿qué estudiante tiene más tareas sin entregar en POO?",
                                     "¿quiénes no han entregado sus tareas?", "alumnos con notas en cero"])
def test_entregas_faltantes_por_estudiante_sin_llm(sincronizado, monkeypatch, mensaje):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, mensaje, course_id=2)
    assert _plan(data) == [("obtener_calificaciones", {"course_id": 2, "ranking": "incidencias"})]
    assert data["respuesta"].startswith(f"En **{POO}**, quien tiene más incidencias es **Carlos Andrés Mendoza "
                                        "Paredes** (1 entrega faltante y 1 nota cero; promedio **2.65/10**, crítico).")
    assert "| Estudiante | Sin entrega | Notas cero | Por calificar | Promedio |" in data["respuesta"]


@pytest.mark.parametrize("mensaje", ["¿cómo va la asistencia de los alumnos de POO?", "¿cuál es el horario de clases?"])
def test_asistencia_u_horarios_no_disponibles(sincronizado, monkeypatch, mensaje):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, mensaje, course_id=2)
    assert data["plan_fuente"] == "dato_no_disponible" and data["herramientas"] == []
    assert data["respuesta"].startswith("La **asistencia** y los **horarios** no forman parte de los datos")


def test_quien_mejoro_mas_entre_unidades_sin_llm(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "¿qué estudiante mejoró más entre unidades?", course_id=2)
    assert _plan(data) == [("obtener_calificaciones", {"course_id": 2, "ranking": "mejora"})]
    filas = data["herramientas"][0]["resultado"]["calificaciones"]
    deltas = [f["variacion"]["delta"] for f in filas]
    assert deltas == sorted(deltas, reverse=True)
    assert "| Estudiante | Unidad inicial | Unidad actual | Variación | Promedio |" in data["respuesta"]
    data = _chat(sincronizado, "¿quién empeoró más?", course_id=2)
    assert _plan(data) == [("obtener_calificaciones", {"course_id": 2, "ranking": "retroceso"})]


def test_mejor_en_un_componente(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "¿quién tiene el mejor promedio en tareas en POO?")
    assert _plan(data) == [("obtener_calificaciones", {"course_id": 2, "extremo": "mejor", "componente": "tareas"})]
    filas = data["herramientas"][0]["resultado"]["calificaciones"]
    assert filas[0]["tareas"] == max(f["tareas"] for f in filas if f["tareas"] is not None)
    assert data["respuesta"].startswith(f"En **{POO}**, el estudiante con la **mayor nota en Tareas (30 %)** es "
                                        f"**{filas[0]['nombres']}**, con **{filas[0]['tareas']:.2f}/10**")


def test_estudiantes_de_un_nivel(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "¿cuántos estudiantes de POO están en nivel crítico y quiénes son?")
    assert _plan(data) == [("obtener_calificaciones", {"course_id": 2, "nivel": "CRITICO"})]
    filas = data["herramientas"][0]["resultado"]["calificaciones"]
    assert filas and all(f["nivel_riesgo"] == "CRITICO" for f in filas)
    assert data["respuesta"].startswith(f"En **{POO}** hay **{len(filas)} estudiante")


def test_materia_por_nombre_parcial(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "dame las notas de programación")
    assert _plan(data)[0] == ("obtener_calificaciones", {"course_id": 2})


# ------------------------------------------------------------------ desambiguación de materia
def _dos_cursos(monkeypatch):
    original = sync_service.cursos_del_docente

    def con_otro(email):
        cursos = original(email)
        if not cursos:
            return cursos
        otro = {**cursos[0], "id": 99, "shortname": "SOF-ED-B", "fullname": "(SOF) ESTRUCTURA DE DATOS - B"}
        return cursos + [otro]

    monkeypatch.setattr(sync_service, "cursos_del_docente", con_otro)


def test_sin_materia_ni_curso_activo_pregunta_de_que_materia(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    _dos_cursos(monkeypatch)
    data = _chat(sincronizado, "¿cuál es el alumno más bajo?")
    assert data["herramientas"] == [] and data["plan_fuente"] == "aclaracion_materia"
    assert data["respuesta"].startswith("¿De qué materia desea consultar el promedio más bajo?")
    assert f"- **{POO}**" in data["respuesta"] and "- **Estructura de datos — Paralelo B**" in data["respuesta"]


def test_con_curso_activo_responde_sobre_ese_curso(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    _dos_cursos(monkeypatch)
    data = _chat(sincronizado, "¿cuál es el alumno más bajo?", course_id=2)
    assert _plan(data) == [("obtener_calificaciones", {"course_id": 2, "extremo": "peor"})]
    assert data["respuesta"].startswith(f"En **{POO}**")              # indica de qué curso son los datos


# ------------------------------------------------------------------ respuesta abierta con datos reales (LLM)
def test_pregunta_abierta_responde_con_datos_reales(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    recibido = {}

    async def llm(pregunta, contexto, lengua):
        recibido.update(pregunta=pregunta, contexto=contexto, lengua=lengua)
        return "**Carlos Andrés Mendoza Paredes** tiene la nota más baja: **2.65/10** (crítico)."

    monkeypatch.setattr(agente_herramientas, "_llm_con_datos", llm)
    data = _chat(sincronizado, "¿qué estudiante de POO necesita más apoyo en la unidad 3?")
    assert data["plan_fuente"] == "ollama_rag" and data["redaccion"] == "llm_restringido_a_datos"
    assert [h["herramienta"] for h in data["herramientas"]] == ["obtener_calificaciones", "identificar_alertas",
                                                               "analizar_actividades"]
    assert all(h["trazabilidad"]["parametros_validados"]["curso"] == "SOF-POO-A" for h in data["herramientas"])
    assert data["respuesta"].startswith("**Carlos Andrés Mendoza Paredes** tiene la nota más baja")
    assert "sólo a partir de los datos sincronizados de Moodle UTA" in data["respuesta"]
    # el LLM sólo recibe datos reales del alcance consultado
    # sólo lo que la pregunta necesita: nota final, nivel, tendencia, promedios por unidad («mejoró entre unidades»)
    linea = next(ln for ln in recibido["contexto"].splitlines() if ln.startswith("- Carlos Andrés Mendoza Paredes:"))
    assert linea.startswith("- Carlos Andrés Mendoza Paredes: nota final 2.65/10; nivel crítico; tendencia a la baja; "
                            "Unidad 1 ")
    assert linea.endswith("; sin entrega 1; notas cero 1; por calificar 0.")
    assert "exámenes" not in linea and "ALERTAS" not in recibido["contexto"]
    assert recibido["pregunta"] == "¿qué estudiante de POO necesita más apoyo en la unidad 3?" and recibido["lengua"] == "es"


def test_respuesta_del_llm_con_cifras_inventadas_se_descarta(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)

    async def llm(pregunta, contexto, lengua):
        return "**Carlos** tiene **9.87/10**."                       # cifra que no está en los datos

    monkeypatch.setattr(agente_herramientas, "_llm_con_datos", llm)
    data = _chat(sincronizado, "¿qué estudiante de POO necesita más apoyo en la unidad 3?")
    # no se muestra lo inventado: se muestran los datos reales del curso con un aviso honesto
    assert data["plan_fuente"] == "datos_relacionados" and "9.87" not in data["respuesta"]
    assert data["respuesta"].startswith("No pude interpretar su pregunta con exactitud, así que no voy a adivinar.")
    assert _plan(data) == [("obtener_calificaciones", {"course_id": 2})]


def test_respuesta_del_llm_con_nombre_mezclado_se_descarta(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)

    async def llm(pregunta, contexto, lengua):
        return "**Carlos Valentina Villacís Naranjo** necesita apoyo: **5.11/10**."   # mezcla de dos estudiantes

    monkeypatch.setattr(agente_herramientas, "_llm_con_datos", llm)
    data = _chat(sincronizado, "¿qué estudiante de POO necesita más apoyo en la unidad 3?")
    assert data["plan_fuente"] == "datos_relacionados" and "Carlos Valentina" not in data["respuesta"]


def test_sin_llm_disponible_pide_precisar(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)                                              # el agente no responde: sin cuelgues
    data = _chat(sincronizado, "¿qué estudiante de POO necesita más apoyo en la unidad 3?")
    assert data["plan_fuente"] == "datos_relacionados"                # datos reales en lugar de adivinar
    data = _chat(sincronizado, "necesito revisar algo")               # sin datos que mostrar: pide precisar
    assert data["plan_fuente"] == "aclaracion" and data["herramientas"] == []


def test_respuesta_fiel():
    datos = "- Carlos | 3.50 | 2.81 | 3.88 | 3.41 | crítico"
    assert agente_herramientas.respuesta_fiel("**Carlos** tiene **3.41/10**.", datos)
    assert not agente_herramientas.respuesta_fiel("**Carlos Valentina** tiene **3.41/10**.", datos)
    assert not agente_herramientas.respuesta_fiel("**Carlos** tiene **3.45/10**.", datos)
    assert not agente_herramientas.respuesta_fiel("", datos)


# ------------------------------------------------------------------ filtro fuera del dominio
@pytest.mark.parametrize("mensaje", ["dame una receta de pan", "¿quién ganó el partido de fútbol?",
                                     "cuéntame un chiste"])
def test_fuera_del_dominio_no_consulta_datos(sincronizado, monkeypatch, mensaje):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, mensaje, course_id=2)
    assert data["respuesta"] == DOMINIO_ES and data["herramientas"] == []


def test_saludo_sigue_siendo_cordial(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "hola")
    assert data["respuesta"].startswith("¡Hola") and data["herramientas"] == []


# ------------------------------------------------------------------ inglés
@pytest.mark.parametrize("mensaje, params, inicio", [
    ("who improved the most in OOP?", {"course_id": 2, "ranking": "mejora"}, "In **Programación orientada a objetos"),
    ("who has the best exams grade in OOP?", {"course_id": 2, "extremo": "mejor", "componente": "acd"},
     "In **Programación orientada a objetos — Section A**, the student with the **highest Exams grade** is"),
])
def test_intenciones_nuevas_en_ingles(sincronizado, monkeypatch, mensaje, params, inicio):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, mensaje)
    assert _plan(data) == [("obtener_calificaciones", params)]
    assert data["respuesta"].startswith(inicio) and data["idioma"] == "en"


def test_ranking_en_ingles(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "give me the ranking of OOP")
    assert _plan(data) == [("obtener_calificaciones", {"course_id": 2, "ranking": "desc"})]
    assert data["respuesta"].startswith("**Grade ranking** in **Programación orientada a objetos — Section A**")
    assert "| # | Student | Average | Level / Trend |" in data["respuesta"]
