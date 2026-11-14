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
    propios = sync_service.cursos_del_docente("rgomez@uta.edu.ec")
    assert totales["cursos"] == len(propios)
    assert totales["estudiantes_unicos"] == len({e["id_number"] for c in propios for e in c["estudiantes"]})
    assert f"**{totales['cursos']} cursos**" in data["respuesta"]
    assert f"**{totales['estudiantes_unicos']} estudiantes únicos**" in data["respuesta"]
    assert data["formato"] == "markdown"


def test_consulta_transversal_de_un_estudiante_ignora_el_curso_activo(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "¿Cómo va Diego Curillo en mis materias?", course_id=2)
    llamada = _herramienta(data, "obtener_calificaciones")
    assert llamada["parametros"] == {"estudiante": "Diego Curillo"}          # sin course_id: todos sus cursos
    cursos_reales = {c["shortname"] for c in sync_service.cursos_del_docente("rgomez@uta.edu.ec")
                     if any(e["id_number"] == "U-04" for e in c["estudiantes"])}
    assert {f["curso"] for f in llamada["resultado"]["calificaciones"]} == cursos_reales
    assert "generar_resumen" not in {h["herramienta"] for h in data["herramientas"]}
    assert data["respuesta"].startswith("**Diego Curillo** (U-04)")


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
    data = _chat(sincronizado, "Prepárame una actividad de refuerzo para Diego Curillo", course_id=2)
    assert [h["herramienta"] for h in data["herramientas"]] == ["proponer_refuerzo"]
    llamada = data["herramientas"][0]
    assert llamada["parametros"] == {"student_query": "Diego Curillo", "course_id": 2}
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
    assert log["detalle"]["parametros"] == {"student_query": "Diego Curillo", "course_id": 2}


def test_refuerzo_sin_curso_elige_el_curso_con_nota_mas_baja(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "Prepara un refuerzo para Diego Curillo")
    r = data["herramientas"][0]["resultado"]
    notas = {c["id"]: e["nota_final"] for c in sync_service.cursos_del_docente("rgomez@uta.edu.ec")
             for e in c["estudiantes"] if e["id_number"] == "U-04"}
    assert r["curso_id"] == min(notas, key=notas.get)


def test_refuerzo_de_estudiante_inexistente_informa_sin_inventar(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "Prepárame un refuerzo para U-77")
    assert data["herramientas"][0]["resultado"]["error"]
    assert data["respuesta"].startswith("No pude completar")


def test_respuesta_estructurada_en_viñetas(sincronizado):  # noqa: F811
    data = _chat(sincronizado, "¿Qué estudiantes de POO necesitan atención?")
    assert "- **Diego Curillo** (SOF-POO-A)" in data["respuesta"]
    assert "; Sebastián" not in data["respuesta"]            # ya no hay listas planas separadas por punto y coma
    data = _chat(sincronizado, "Dame un resumen y las alertas de POO")
    assert data["respuesta"].startswith("**Resumen ejecutivo**")
    assert "### Resumen de SOF-POO-A" in data["respuesta"] and "### Alertas tempranas" in data["respuesta"]


def test_plan_del_llm_de_refuerzo_usa_el_estudiante_mencionado(sincronizado, monkeypatch):  # noqa: F811
    real = httpx.AsyncClient

    def handler(request):
        return httpx.Response(200, json={"fuente": "ollama_slm", "llamadas": [
            {"herramienta": "proponer_refuerzo", "parametros": {"student_query": "Camila"}},
            {"herramienta": "generar_resumen", "parametros": {"course_id": 2}}]})

    monkeypatch.setattr(agente_herramientas.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    data = _chat(sincronizado, "Prepárame una actividad de refuerzo para Diego Curillo")
    assert data["plan_fuente"] == "ollama_slm"
    assert [h["herramienta"] for h in data["herramientas"]] == ["proponer_refuerzo"]
    assert data["herramientas"][0]["parametros"]["student_query"] == "Diego Curillo"


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
