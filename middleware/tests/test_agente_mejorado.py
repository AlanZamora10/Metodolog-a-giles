"""
Pulido final del agente: respuestas estructuradas, consultas transversales a todos los cursos del docente,
rendimiento por actividad y propuesta de refuerzo (proponer_refuerzo) basada en falencias reales.
"""

import httpx
from fastapi.testclient import TestClient

from app import repositories
from app.main import app
from app.services import agente_herramientas, sync_service

from test_fase_a import sincronizado  # noqa: F401 (fixture)

client = TestClient(app)


def _chat(headers, mensaje, **extra):
    res = client.post("/api/v1/agent/chat", headers=headers, json={"mensaje": mensaje, **extra})
    assert res.status_code == 200, res.text
    return res.json()


def _herramienta(data, nombre):
    return next(h for h in data["herramientas"] if h["herramienta"] == nombre)


def test_totales_de_cursos_y_estudiantes(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "¿Cuántos cursos y estudiantes tengo en total?", course_id=2)
    assert [h["herramienta"] for h in data["herramientas"]] == ["listar_cursos_autorizados"]
    totales = _herramienta(data, "listar_cursos_autorizados")["resultado"]["totales"]
    propios = sync_service.cursos_del_docente("rgomez4824@uta.edu.ec")
    assert totales["cursos"] == len(propios)
    assert totales["estudiantes_unicos"] == len({e["id_number"] for c in propios for e in c["estudiantes"]})
    assert f"**{totales['cursos']} cursos**" in data["respuesta"]
    assert f"**{totales['estudiantes_unicos']} estudiantes únicos**" in data["respuesta"]
    assert data["formato"] == "markdown"


def test_consulta_transversal_de_un_estudiante_ignora_el_curso_activo(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "¿Cómo va Carlos Mendoza en mis materias?", course_id=2)
    llamada = _herramienta(data, "obtener_calificaciones")
    assert llamada["parametros"] == {"estudiante": "Carlos Andrés Mendoza Paredes"}          # sin course_id: todos sus cursos
    cursos_reales = {c["shortname"] for c in sync_service.cursos_del_docente("rgomez4824@uta.edu.ec")
                     if any(e["id_number"] == "U-04" for e in c["estudiantes"])}
    assert {f["curso"] for f in llamada["resultado"]["calificaciones"]} == cursos_reales
    assert "generar_resumen" not in {h["herramienta"] for h in data["herramientas"]}
    assert data["respuesta"].startswith("**Carlos Andrés Mendoza Paredes** (U-04)")


def test_actividades_con_menor_rendimiento_ordenadas_y_sin_inventar(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "¿Qué actividades tienen menor rendimiento en POO?")
    llamada = _herramienta(data, "analizar_actividades")
    assert llamada["parametros"] == {"course_id": 2}
    acts = [a for a in llamada["resultado"]["actividades"] if a["promedio"] is not None]
    assert [a["promedio"] for a in acts] == sorted(a["promedio"] for a in acts)
    # El promedio informado coincide con las notas sincronizadas de esa actividad
    curso = next(c for c in sync_service.SYNC_STATE["cursos"] if c["id"] == 2)
    notas = [a["nota"] for e in curso["estudiantes"] for a in e["actividades"]
             if a["id_number"] == acts[0]["actividad"] and a["nota"] is not None]
    assert acts[0]["promedio"] == round(sum(notas) / len(notas), 2)
    assert f"{acts[0]['actividad']}" in data["respuesta"] and f"{acts[0]['promedio']:.2f}/10" in data["respuesta"]


def test_proponer_refuerzo_con_falencias_reales(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "Prepárame una actividad de refuerzo para Carlos Mendoza", course_id=2)
    assert [h["herramienta"] for h in data["herramientas"]] == ["proponer_refuerzo"]
    llamada = data["herramientas"][0]
    assert llamada["parametros"] == {"student_query": "Carlos Andrés Mendoza Paredes", "course_id": 2}
    r = llamada["resultado"]
    assert r["curso_id"] == 2 and r["estudiante"]["id_number"] == "U-04"
    assert {"titulo", "objetivo", "pasos", "criterios", "instrucciones"} <= set(r["propuesta"])
    assert sum(c["peso"] for c in r["propuesta"]["criterios"]) == 100
    assert ("U2-T4", "SIN_ENTREGA") in {(i["actividad"], i["tipo"]) for i in r["evidencia"]["incidencias"]}
    assert ("U1-T2", "NOTA_0") in {(i["actividad"], i["tipo"]) for i in r["evidencia"]["incidencias"]}
    assert "U2-T4" in r["propuesta"]["instrucciones"]
    alerta = next(a for a in repositories.list_alertas(course_id=2) if a["id_number"] == "U-04")
    assert r["alerta"]["id"] == alerta["id"]
    est = next(e for e in next(c for c in sync_service.SYNC_STATE["cursos"] if c["id"] == 2)["estudiantes"]
               if e["id_number"] == "U-04")
    assert r["evidencia"]["nota_final"] == est["nota_final"]
    for texto in ("**Título:**", "**Objetivo:**", "**Descripción de la tarea**", "**Criterios de evaluación**",
                  f"{est['nota_final']:.2f}/10", "Centro de alertas"):
        assert texto in data["respuesta"]

    log = [x for x in repositories.filas("logs_sistema") if x["tipo_proceso"] == "AGENTE_HERRAMIENTA"][-1]
    assert log["detalle"]["herramienta"] == "proponer_refuerzo"
    assert log["detalle"]["parametros"] == {"student_query": "Carlos Andrés Mendoza Paredes", "course_id": 2}


def test_refuerzo_sin_curso_elige_el_curso_con_nota_mas_baja(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "Prepara un refuerzo para Carlos Mendoza")
    r = data["herramientas"][0]["resultado"]
    notas = {c["id"]: e["nota_final"] for c in sync_service.cursos_del_docente("rgomez4824@uta.edu.ec")
             for e in c["estudiantes"] if e["id_number"] == "U-04"}
    assert r["curso_id"] == min(notas, key=notas.get)


def test_refuerzo_de_estudiante_inexistente_informa_sin_inventar(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "Prepárame un refuerzo para U-77")
    assert data["herramientas"][0]["resultado"]["error"]
    assert data["respuesta"].startswith("No pude completar")


def test_respuesta_estructurada_en_viñetas(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "¿Qué estudiantes de POO necesitan atención?")
    assert "- **Carlos Andrés Mendoza Paredes** (Programación orientada a objetos, paralelo A)" in data["respuesta"]
    assert "SOF-POO-A" not in data["respuesta"]
    assert "; Sebastián" not in data["respuesta"]            # ya no hay listas planas separadas por punto y coma
    data = _chat(sincronizado, "Dame un resumen y las alertas de POO")
    assert data["respuesta"].startswith("**Resumen ejecutivo**")
    assert "### Resumen de Programación orientada a objetos, paralelo A" in data["respuesta"] and "### Alertas tempranas" in data["respuesta"]


def test_plan_del_llm_de_refuerzo_usa_el_estudiante_mencionado(sincronizado, monkeypatch):  # noqa: F811
    real = httpx.AsyncClient

    def handler(request):
        return httpx.Response(200, json={"fuente": "ollama_slm", "llamadas": [
            {"herramienta": "proponer_refuerzo", "parametros": {"student_query": "Camila"}},
            {"herramienta": "generar_resumen", "parametros": {"course_id": 2}}]})

    monkeypatch.setattr(agente_herramientas.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    data = _chat(sincronizado, "Prepárame una actividad de refuerzo para Carlos Mendoza")
    assert data["plan_fuente"] == "ollama_slm"
    assert [h["herramienta"] for h in data["herramientas"]] == ["proponer_refuerzo"]
    assert data["herramientas"][0]["parametros"]["student_query"] == "Carlos Andrés Mendoza Paredes"


def test_catalogo_expone_las_seis_herramientas(sincronizado):  # noqa: F811
    nombres = [h["nombre"] for h in client.get("/api/v1/agent/herramientas", headers=sincronizado).json()]
    assert nombres == ["listar_cursos_autorizados", "obtener_calificaciones", "identificar_alertas",
                       "generar_resumen", "analizar_actividades", "proponer_refuerzo"]


def test_refuerzo_propuesto_por_el_llm_sin_pedido_explicito_se_descarta(sincronizado, monkeypatch):  # noqa: F811
    real = httpx.AsyncClient

    def handler(request):
        return httpx.Response(200, json={"fuente": "ollama_slm", "llamadas": [
            {"herramienta": "proponer_refuerzo",
             "parametros": {"student_query": "¿Cuántos cursos y estudiantes tengo en total?", "course_id": 2}}]})

    monkeypatch.setattr(agente_herramientas.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    data = _chat(sincronizado, "¿Cuántos cursos y estudiantes tengo en total?")
    assert data["plan_fuente"] == "reglas_deterministas"
    assert [h["herramienta"] for h in data["herramientas"]] == ["listar_cursos_autorizados"]


import pytest  # noqa: E402


@pytest.mark.parametrize("mensaje,esperado", [
    ("Hola", "¡Hola"), ("buenos días", "¡Hola"), ("¡Gracias!", "Con gusto"), ("ok", "Perfecto"),
    ("muchas gracias, muy amable", "Con gusto"), ("chao", "¡Hasta pronto"),
])
def test_saludos_y_cortesias_sin_herramientas(sincronizado, monkeypatch, mensaje, esperado):  # noqa: F811
    def no_llamar(**kw):
        raise AssertionError("una cortesía no debe consultar al LLM")

    monkeypatch.setattr(agente_herramientas.httpx, "AsyncClient", no_llamar)
    data = _chat(sincronizado, mensaje, course_id=2)
    assert data["herramientas"] == [] and data["plan_fuente"] == "cortesia"
    assert data["respuesta"].startswith(esperado) and len(data["respuesta"]) < 220
    logs = [x for x in repositories.filas("logs_sistema") if x["tipo_proceso"] == "AGENTE_HERRAMIENTA"]
    chat = repositories.filas("logs_sistema")[-1]
    assert chat["tipo_proceso"] == "AGENTE_CHAT" and chat["detalle"]["herramientas"] == []
    assert all(x["detalle"].get("plan") != "cortesia" for x in logs)


def test_cortesia_con_consulta_si_ejecuta_herramientas(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "Hola, ¿qué estudiantes de POO necesitan atención?")
    assert [h["herramienta"] for h in data["herramientas"]] == ["identificar_alertas"]


def test_conteo_responde_solo_cifras_y_lista_compacta(sincronizado, monkeypatch):  # noqa: F811
    real = httpx.AsyncClient

    def handler(request):  # el LLM intenta anexar un informe completo
        return httpx.Response(200, json={"fuente": "ollama_slm", "llamadas": [
            {"herramienta": "listar_cursos_autorizados", "parametros": {}},
            {"herramienta": "generar_resumen", "parametros": {}},
            {"herramienta": "identificar_alertas", "parametros": {}}]})

    monkeypatch.setattr(agente_herramientas.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    data = _chat(sincronizado, "¿Cuántos cursos o estudiantes tengo en total?", course_id=2)
    assert [h["herramienta"] for h in data["herramientas"]] == ["listar_cursos_autorizados"]
    assert data["plan_fuente"] == "ollama_slm"
    for prohibido in ("alerta", "Recomendaci", "crítico", "promedio", "Resumen ejecutivo"):
        assert prohibido not in data["respuesta"]
    assert data["respuesta"].count("\n- **") == data["herramientas"][0]["resultado"]["totales"]["cursos"]


def test_resumen_general_cubre_todos_los_cursos(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "Dame un resumen general", course_id=2)
    resumen = _herramienta(data, "generar_resumen")
    assert resumen["parametros"] == {}
    assert len(resumen["resultado"]["resumenes"]) == len(sync_service.cursos_del_docente("rgomez4824@uta.edu.ec"))


def test_mensaje_sin_intencion_pide_precisar_sin_lanzar_informes(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "necesito revisar algo", course_id=2)
    assert data["herramientas"] == [] and data["plan_fuente"] == "aclaracion"
    assert "resumen general" in data["respuesta"]


def test_sincronizacion_trae_la_cedula_del_perfil_de_moodle(sincronizado):  # noqa: F811
    data = client.get("/api/cursos/2/estudiantes", headers=sincronizado).json()
    cedulas = {e["id_number"]: e["cedula"] for e in data["estudiantes"]}
    assert cedulas["U-04"] == "1804923199" and cedulas["U-03"] == "0503128746"
    resumen = client.get("/api/sincronizacion", headers=sincronizado).json()["estudiantes"]
    assert {e["id_number"]: e["cedula"] for e in resumen}["U-04"] == "1804923199"


@pytest.mark.parametrize("mensaje", [
    "Dame el plan de estudio para Carlos Mendoza",
    "¿Cómo ayudarlo? Me refiero a Carlos Mendoza",
    "Necesito un plan de apoyo para Carlos Mendoza",
    "plan de apoyo para 1804923199",
])
def test_frases_de_plan_de_apoyo_activan_proponer_refuerzo(sincronizado, mensaje):  # noqa: F811
    data = _chat(sincronizado, mensaje, course_id=2)
    assert [h["herramienta"] for h in data["herramientas"]] == ["proponer_refuerzo"]
    assert data["herramientas"][0]["parametros"]["student_query"] == "Carlos Andrés Mendoza Paredes"
    assert "generar_resumen" not in {h["herramienta"] for h in data["herramientas"]}


def test_plan_de_apoyo_sin_estudiante_pregunta_por_el(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "¿Cómo puedo ayudarlo?", course_id=2)
    assert data["herramientas"] == [] and "cédula" in data["respuesta"]


def test_respuestas_del_agente_sin_codigos_tecnicos(sincronizado):  # noqa: F811
    for mensaje in ("¿Qué estudiantes de POO necesitan atención?", "Dame las notas de Carlos Mendoza",
                    "Prepárame un refuerzo para Carlos Mendoza"):
        texto = _chat(sincronizado, mensaje)["respuesta"]
        for codigo in ("R1", "R2", "ACD", "PAE", "SIN_ENTREGA"):
            assert codigo not in texto, (mensaje, codigo)
    assert "Exámenes" in _chat(sincronizado, "Dame las notas de Carlos Mendoza")["respuesta"]


# ------------------------------------------------------------------ Nombres completos (dos nombres y dos apellidos)
_CURSOS_NOMBRES = [{"estudiantes": [
    {"id_number": "U-04", "nombres": "Carlos Andrés Mendoza Paredes", "cedula": "1804923199"},
    {"id_number": "U-05", "nombres": "Marco Antonio Paredes Velasco", "cedula": "1704561230"},
    {"id_number": "U-07", "nombres": "Carlos Eduardo Mena Castillo", "cedula": "1802764553"},
]}]


@pytest.mark.parametrize("mensaje, esperado", [
    ("¿Cómo va Carlos Mendoza?", "Carlos Andrés Mendoza Paredes"),            # nombre parcial
    ("Notas de Carlos Andrés Mendoza Paredes", "Carlos Andrés Mendoza Paredes"),
    ("¿Y Marco Paredes?", "Marco Antonio Paredes Velasco"),                    # Paredes es 2.º apellido de Carlos
    ("Revisa a Mendoza", "Carlos Andrés Mendoza Paredes"),                     # un apellido largo y único
    ("¿Cómo va Paredes?", None),                                               # apellido compartido: ambiguo
    ("¿Y Carlos?", None),                                                      # dos estudiantes se llaman Carlos
])
def test_estudiante_mencionado_con_nombres_completos(mensaje, esperado):
    texto = agente_herramientas._normalizar(mensaje)
    assert agente_herramientas._estudiante_mencionado(texto, _CURSOS_NOMBRES) == esperado


def test_filtro_por_parte_del_nombre_completo():
    carlos = _CURSOS_NOMBRES[0]["estudiantes"][0]
    for filtro in ("carlos mendoza", "mendoza paredes", "carlos andres mendoza paredes", "u-04", "1804923199"):
        assert agente_herramientas._coincide(carlos, filtro), filtro
    assert not agente_herramientas._coincide(carlos, "carlos mena")


# ------------------------------------------------------------------ Umbral numérico estricto
def _notas(sincronizado):  # noqa: F811
    propios = sync_service.cursos_del_docente("rgomez4824@uta.edu.ec")
    return sorted((e["nota_final"], e["nombres"]) for c in propios for e in c["estudiantes"])


@pytest.mark.parametrize("mensaje, cumple, texto", [
    ("De mis materias qué estudiantes están con una nota menor de 4 puntos", lambda n: n < 4, "nota menor a 4.00"),
    ("¿Quiénes tienen promedio mayor a 7?", lambda n: n > 7, "nota mayor a 7.00"),
    ("Estudiantes con nota entre 6 y 7", lambda n: 6 <= n <= 7, "nota entre 6.00 y 7.00"),
    ("notas menores o iguales a 6,5", lambda n: n <= 6.5, "nota menor o igual a 6.50"),
])
def test_umbral_explicito_filtra_estrictamente(sincronizado, mensaje, cumple, texto):  # noqa: F811
    data = _chat(sincronizado, mensaje, course_id=2)
    assert [h["herramienta"] for h in data["herramientas"]] == ["obtener_calificaciones"]
    filas = data["herramientas"][0]["resultado"]["calificaciones"]
    esperadas = [x for x in _notas(sincronizado) if cumple(round(x[0], 2))]
    assert [(f["nota_final"], f["nombres"]) for f in filas] == esperadas          # sólo quienes cumplen, de menor a mayor
    assert data["respuesta"].startswith(f"Encontré **{len(esperadas)} matrícula(s)** con **{texto}**")
    lineas = [ln for ln in data["respuesta"].splitlines() if ln.startswith("- ")]
    assert len(lineas) == len(esperadas)


def test_umbral_sin_coincidencias_lo_dice_sin_listar(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "¿Quién tiene nota menor a 1?")
    assert data["herramientas"][0]["resultado"]["calificaciones"] == []
    assert data["respuesta"].startswith("Ninguna matrícula tiene **nota menor a 1.00**")


def test_umbral_respeta_la_materia_nombrada(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "En Programación orientada a objetos, ¿quiénes tienen nota menor de 4?")
    assert data["herramientas"][0]["parametros"] == {"course_id": 2, "operador": "<", "umbral": 4.0}
    assert "en Programación orientada a objetos, paralelo A" in data["respuesta"]


def test_el_umbral_del_llm_no_prevalece_sobre_el_mensaje(sincronizado, monkeypatch):  # noqa: F811
    from test_fase_a import _agente_responde
    _agente_responde(monkeypatch, {"fuente": "ollama_slm", "llamadas": [
        {"herramienta": "obtener_calificaciones", "parametros": {"operador": "<", "umbral": 7}}]})
    data = _chat(sincronizado, "Dame las notas de POO")
    assert "operador" not in data["herramientas"][0]["parametros"]


# ------------------------------------------------------------------ Materias no son estudiantes
def test_materia_pasada_como_estudiante_por_el_llm_consulta_el_curso(sincronizado, monkeypatch):  # noqa: F811
    from test_fase_a import _agente_responde
    _agente_responde(monkeypatch, {"fuente": "ollama_slm", "llamadas": [
        {"herramienta": "obtener_calificaciones", "parametros": {"estudiante": "Programación orientada a objetos"}}]})
    data = _chat(sincronizado, "Dame las notas de Programación orientada a objetos, paralelo A")
    [llamada] = data["herramientas"]
    assert llamada["parametros"] == {"course_id": 2}
    assert "error" not in llamada["resultado"] and llamada["resultado"]["filas"] == 4
    assert "No se encontró al estudiante" not in data["respuesta"]


def test_palabras_de_materias_no_cuentan_como_nombre_de_estudiante():
    cursos = [{"id": 2, "shortname": "SOF-ED-B", "fullname": "(SOF) ESTRUCTURA DE DATOS - B", "estudiantes": [
        {"id_number": "U-50", "nombres": "Ana Lucía Datos Estructura", "cedula": None}]}]
    texto = agente_herramientas._normalizar("¿Cómo va Estructura de datos?")
    assert agente_herramientas._estudiante_mencionado(texto, cursos) is None
    assert agente_herramientas._curso_mencionado(texto, cursos) == 2


def test_paralelo_distingue_cursos_de_la_misma_materia():
    cursos = [{"id": 7, "shortname": "SOF-ED-A", "fullname": "(SOF) ESTRUCTURA DE DATOS - A"},
              {"id": 3, "shortname": "SOF-ED-B", "fullname": "(SOF) ESTRUCTURA DE DATOS - B"}]
    texto = agente_herramientas._normalizar("Resumen de Estructura de datos, paralelo B")
    assert agente_herramientas._curso_mencionado(texto, cursos) == 3


# ------------------------------------------------------------------ Respuestas rápidas y lenguaje natural
def _sin_llm(monkeypatch):
    def no_llamar(**kw):
        raise AssertionError("esta consulta no debe esperar al LLM")

    monkeypatch.setattr(agente_herramientas.httpx, "AsyncClient", no_llamar)


@pytest.mark.parametrize("mensaje", ["¿Qué puedes hacer?", "ayuda", "¿Quién eres?", "Hola, ¿en qué me puedes ayudar?",
                                     "¿Cómo funciona?"])
def test_preguntas_sobre_el_asistente_responden_al_instante(sincronizado, monkeypatch, mensaje):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, mensaje)
    assert data["herramientas"] == [] and data["plan_fuente"] == "cortesia"
    assert data["respuesta"].startswith("Soy su Asistente Académico de EduMonitor AI, Roberto Gómez.")
    ejemplos = [ln for ln in data["respuesta"].splitlines() if ln.startswith("- «")]
    assert len(ejemplos) == 3 and "«¿Cómo van mis cursos?»" in ejemplos[0]
    assert "Programación orientada a objetos" in data["respuesta"]           # ejemplo con su materia real


def test_saludo_usa_el_nombre_del_docente_y_sugiere_ejemplos(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "Buenas tardes")
    assert data["respuesta"].startswith("¡Hola, Roberto Gómez! ¿En qué le ayudo hoy?")
    assert "«Prepárame un plan de apoyo para Carlos Mendoza»" in data["respuesta"]  # su estudiante más crítico


@pytest.mark.parametrize("mensaje, herramienta, parametros", [
    ("cómo van mis cursos", "generar_resumen", {}),
    ("resumen general", "generar_resumen", {}),
    ("quién está mal", "identificar_alertas", {"course_id": 2}),
    ("hay alertas?", "identificar_alertas", {"course_id": 2}),
    ("¿Qué estudiantes de POO tienen problemas con las tareas este parcial?", "identificar_alertas", {"course_id": 2}),
    ("dame los reprobados", "obtener_calificaciones", {"course_id": 2, "operador": "<", "umbral": 7.0}),
    ("¿Quiénes están aprobando en todas mis materias?", "obtener_calificaciones", {"operador": ">=", "umbral": 7.0}),
])
def test_frases_informales_se_resuelven_sin_esperar_al_llm(sincronizado, monkeypatch, mensaje, herramienta,
                                                           parametros):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, mensaje, course_id=2)
    assert [(h["herramienta"], h["parametros"]) for h in data["herramientas"]] == [(herramienta, parametros)]
    assert data["plan_fuente"] == "reglas_deterministas"


def test_reprobados_lista_solo_notas_bajo_siete(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "dame los reprobados", course_id=2)
    filas = data["herramientas"][0]["resultado"]["calificaciones"]
    assert filas and all(f["nota_final"] < 7 for f in filas)
    assert data["respuesta"].startswith(f"Encontré **{len(filas)} matrícula(s)** con **nota menor a 7.00**")


@pytest.mark.parametrize("mensaje, esperado", [
    ("notas de carlos mendosa", "Carlos Andrés Mendoza Paredes"),            # z -> s
    ("¿como va sebastian romro?", "Sebastián Alejandro Romero Haro"),        # sin tilde y una letra omitida
    ("notas de camila", "Camila Alejandra Andrade Morales"),                 # nombre único: basta el primero
])
def test_nombres_parciales_sin_tildes_o_con_errores_menores(sincronizado, mensaje, esperado):  # noqa: F811
    data = _chat(sincronizado, mensaje)
    assert data["herramientas"][0]["parametros"]["estudiante"] == esperado


def test_nombre_ambiguo_pide_aclaracion_con_opciones(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)
    data = _chat(sincronizado, "¿Cómo va Andrés?")
    assert data["herramientas"] == [] and data["plan_fuente"] == "aclaracion"
    assert data["respuesta"].startswith("¿A qué estudiante se refiere:")
    assert "**Carlos Andrés Mendoza Paredes**" in data["respuesta"] and "**Andrés Felipe Salazar Cueva**" in data["respuesta"]


def test_mensaje_poco_claro_pide_precisar_en_una_frase_amable(sincronizado, monkeypatch):  # noqa: F811
    _sin_llm(monkeypatch)                                   # mensaje corto: no se espera a Ollama
    data = _chat(sincronizado, "necesito revisar algo")
    assert data["respuesta"].startswith("No estoy seguro de qué necesita, Roberto Gómez.")
    assert data["respuesta"].count("\n") == 0


def test_si_ollama_no_responde_a_tiempo_responden_las_reglas(sincronizado, monkeypatch):  # noqa: F811
    real = httpx.AsyncClient

    def handler(request):
        raise httpx.ReadTimeout("Ollama tardó demasiado", request=request)

    monkeypatch.setattr(agente_herramientas.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    data = _chat(sincronizado, "¿Qué estudiantes de POO necesitan atención esta semana?")
    assert data["plan_fuente"] == "reglas_deterministas"
    assert [h["herramienta"] for h in data["herramientas"]] == ["identificar_alertas"]
    assert agente_herramientas.AGENT_CHAT_TIMEOUT_SECONDS <= 6
