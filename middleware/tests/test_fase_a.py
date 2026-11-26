"""
Fase A — SQL Server, publicación real en Moodle, reporte del curso y chat del agente con herramientas.

Moodle se simula (sincronización, login, local_edumonitor_publicar_refuerzo y local_edumonitor_notificar_refuerzo); la base es SQLite en memoria
salvo que se ejecute con TEST_DATABASE_URL (p. ej. SQL Server real en Docker).
"""

from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateIndex, CreateTable

from app import database, repositories
from app.config import database_url, settings
from app.main import app
from app.routers import alerts as alerts_router
from app.services import agente_herramientas, sync_service
from app.services.moodle_client import MoodleError
from moodle_fake import DOCENTE, FakeMoodleSprint3

client = TestClient(app)


# =============================================================================== Esquema T-SQL
def _ddl_mssql():
    return {t.name: str(CreateTable(t).compile(dialect=mssql.dialect())) for t in database.metadata.sorted_tables}


def test_esquema_tsql_tipos_sql_server():
    ddl = _ddl_mssql()
    assert len(ddl) == 13                                    # incluye materiales_curso (PDF de clase)
    assert "NVARCHAR(255)" in ddl["materiales_curso"]
    assert "IDENTITY" in ddl["usuarios"]
    assert "NVARCHAR(max)" in ddl["logs_sistema"]            # mensaje (texto) y detalle (JSON)
    assert "DATETIME2" in ddl["logs_sistema"] and "DATETIME2" in ddl["refuerzos"]
    assert "BIT" in ddl["usuarios"] and "BIT" in ddl["alertas_tempranas"]
    assert "NVARCHAR(120)" in ddl["estudiantes"]             # nombres con tildes
    assert all("CASCADE" not in sentencia for sentencia in ddl.values())  # sin rutas de cascada múltiples


def test_unicidad_de_alertas_es_indice_filtrado():
    indice = next(i for i in database.alertas_tempranas.indexes if i.name == "ux_alertas_estudiante_regla")
    sql = str(CreateIndex(indice).compile(dialect=mssql.dialect()))
    assert "UNIQUE" in sql and "WHERE regla IS NOT NULL" in sql


def test_url_sql_server_desde_variables(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "")
    monkeypatch.setattr(settings, "MSSQL_HOST", "sqlserver")
    monkeypatch.setattr(settings, "MSSQL_USER", "sa")
    monkeypatch.setattr(settings, "MSSQL_PASSWORD", "Clave@Con#Simbolos")
    monkeypatch.setattr(settings, "MSSQL_DB", "MoodleUTADB")
    url = database_url()
    assert url.startswith("mssql+pyodbc://sa:")
    assert "@sqlserver:1433/MoodleUTADB" in url
    assert "Clave%40Con%23Simbolos" in url                   # contraseña escapada
    assert "TrustServerCertificate=yes" in url and "ODBC+Driver+18+for+SQL+Server" in url


# =============================================================================== Fixtures
@pytest.fixture
def sincronizado(monkeypatch):
    database.use_engine(database.new_sqlite_engine(), "sqlite_prueba")
    sync_service.SYNC_STATE.update({"ultima_sincronizacion": None, "moodle": None, "cursos": []})
    monkeypatch.setattr(sync_service, "MoodleClient", lambda: FakeMoodleSprint3())
    res = client.post("/api/v1/auth/login", json=DOCENTE)
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    assert client.post("/api/sincronizacion", headers=headers).status_code == 200
    yield headers


class FakeMoodlePublicacion:
    llamadas = []
    avisos = []
    falla = False
    falla_aviso = False

    def __init__(self):
        pass

    async def publicar_refuerzo(self, **kw):
        if FakeMoodlePublicacion.falla:
            raise MoodleError("local_edumonitor_publicar_refuerzo: El estudiante no está matriculado (activo) en el curso.")
        existente = any(llamada["codigo"] == kw["codigo"] for llamada in FakeMoodlePublicacion.llamadas)
        FakeMoodlePublicacion.llamadas.append(kw)
        cmid = 700 + int(kw["codigo"].split("-")[1])
        return {"cmid": cmid, "url": f"http://localhost:8080/mod/assign/view.php?id={cmid}", "seccion": 4,
                "existente": existente, "archivo": kw.get("pdf_nombre") if kw.get("pdf_base64") else ""}

    async def notificar_refuerzo(self, **kw):
        if FakeMoodlePublicacion.falla_aviso:
            raise MoodleError("local_edumonitor_notificar_refuerzo: No se pudo enviar la notificación del refuerzo.")
        existente = any(a["cmid"] == kw["cmid"] for a in FakeMoodlePublicacion.avisos)
        FakeMoodlePublicacion.avisos.append(kw)
        return {"notificacionid": 500 + kw["cmid"], "existente": existente}


@pytest.fixture
def moodle_publicacion(monkeypatch):
    FakeMoodlePublicacion.llamadas, FakeMoodlePublicacion.falla = [], False
    FakeMoodlePublicacion.avisos, FakeMoodlePublicacion.falla_aviso = [], False
    monkeypatch.setattr(alerts_router, "MoodleClient", FakeMoodlePublicacion)
    yield FakeMoodlePublicacion


def _alerta(headers, id_number):
    return next(a for a in client.get("/api/v1/alertas", params={"course_id": 2}, headers=headers).json()
                if a["id_number"] == id_number)


# =============================================================================== Publicación real
def test_publicar_crea_tarea_real_en_moodle(sincronizado, moodle_publicacion):
    alerta = _alerta(sincronizado, "U-04")
    refuerzo = client.post(f"/api/v1/alertas/{alerta['id']}/atender", headers=sincronizado).json()["refuerzo"]

    res = client.post(f"/api/v1/refuerzos/{refuerzo['id']}/publicar", headers=sincronizado,
                      json={"confirmado": True, "titulo": "Refuerzo Tareas U2", "fecha_entrega": "2099-01-15"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["cmid"] == 700 + refuerzo["id"]               # cmid REAL devuelto por Moodle (sin simulación)
    assert data["moodle_link"].endswith(f"id={data['cmid']}")
    assert data["fecha_entrega"] == "2099-01-15T23:59:00-05:00"

    llamada = moodle_publicacion.llamadas[0]
    assert llamada["course_id"] == 2
    assert llamada["email_estudiante"] == "cmendoza3199@uta.edu.ec"   # visible sólo para ese estudiante
    assert llamada["nombre"] == "Refuerzo Tareas U2"
    assert llamada["codigo"] == f"REF-{refuerzo['id']}"
    assert llamada["fecha_entrega"] == int(datetime(2099, 1, 16, 4, 59, tzinfo=timezone.utc).timestamp())

    guardado = repositories.get_refuerzo(refuerzo_id=refuerzo["id"])
    assert guardado["estado"] == "PUBLICADO" and guardado["cmid"] == data["cmid"]
    assert guardado["moodle_url"] == data["moodle_link"]
    assert _alerta(sincronizado, "U-04")["estado"] == "PUBLICADO"
    log = repositories.filas("logs_sistema")[-1]
    assert log["tipo_proceso"] == "PUBLICAR_REFUERZO" and log["estado"] == "EXITO" and log["detalle"]["cmid"] == data["cmid"]


def test_publicar_adjunta_la_guia_de_estudio_en_pdf(sincronizado, moodle_publicacion):
    import base64
    alerta = _alerta(sincronizado, "U-04")
    refuerzo = client.post(f"/api/v1/alertas/{alerta['id']}/atender", headers=sincronizado).json()["refuerzo"]
    res = client.post(f"/api/v1/refuerzos/{refuerzo['id']}/publicar", headers=sincronizado,
                      json={"confirmado": True, "instrucciones": "Resuelva la guía adjunta."})
    assert res.status_code == 200, res.text
    llamada = moodle_publicacion.llamadas[0]
    pdf = base64.b64decode(llamada["pdf_base64"], validate=True)
    assert pdf.startswith(b"%PDF-") and len(pdf) > 5000
    assert llamada["pdf_nombre"].startswith("Guia_refuerzo_POO_U") and llamada["pdf_nombre"].endswith("_U-04.pdf")
    assert llamada["instrucciones"].startswith("Resuelva la guía adjunta.")
    assert f"descargue el PDF adjunto «{llamada['pdf_nombre']}»" in llamada["instrucciones"]
    assert res.json()["guia_pdf"] == llamada["pdf_nombre"]
    # En la base quedan las instrucciones del docente, sin la nota del adjunto
    assert repositories.get_refuerzo(refuerzo_id=refuerzo["id"])["instrucciones"] == "Resuelva la guía adjunta."
    assert repositories.filas("logs_sistema")[-1]["detalle"]["guia_pdf"] == llamada["pdf_nombre"]


def test_si_falla_la_guia_la_tarea_se_publica_sin_adjunto(sincronizado, moodle_publicacion, monkeypatch):
    def falla(**_):
        raise RuntimeError("fuente no disponible")

    monkeypatch.setattr(alerts_router, "generar_guia_pdf", falla)
    alerta = _alerta(sincronizado, "U-04")
    refuerzo = client.post(f"/api/v1/alertas/{alerta['id']}/atender", headers=sincronizado).json()["refuerzo"]
    res = client.post(f"/api/v1/refuerzos/{refuerzo['id']}/publicar", headers=sincronizado, json={"confirmado": True})
    assert res.status_code == 200, res.text
    assert moodle_publicacion.llamadas[0]["pdf_base64"] == "" and res.json()["guia_pdf"] is None
    assert any(log["tipo_proceso"] == "GUIA_REFUERZO" and log["estado"] == "ERROR"
               for log in repositories.filas("logs_sistema"))


def test_publicar_notifica_al_estudiante_en_la_campana_de_moodle(sincronizado, moodle_publicacion):
    alerta = _alerta(sincronizado, "U-04")
    refuerzo = client.post(f"/api/v1/alertas/{alerta['id']}/atender", headers=sincronizado).json()["refuerzo"]
    res = client.post(f"/api/v1/refuerzos/{refuerzo['id']}/publicar", headers=sincronizado,
                      json={"confirmado": True, "instrucciones": "Resuelva los ejercicios 1 a 5 de la Unidad 2."})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["notificado"] is True and data["notificacion_id"] == 500 + data["cmid"]
    assert "campana de notificaciones" in data["mensaje"]

    [aviso] = moodle_publicacion.avisos
    assert aviso == {"cmid": data["cmid"], "email_estudiante": "cmendoza3199@uta.edu.ec",
                     "indicaciones": "Resuelva los ejercicios 1 a 5 de la Unidad 2.",
                     "email_docente": "rgomez4824@uta.edu.ec"}
    assert repositories.filas("logs_sistema")[-1]["detalle"]["notificado"] is True


def test_si_falla_el_aviso_la_tarea_queda_publicada_y_se_audita(sincronizado, moodle_publicacion):
    alerta = _alerta(sincronizado, "U-04")
    refuerzo = client.post(f"/api/v1/alertas/{alerta['id']}/atender", headers=sincronizado).json()["refuerzo"]
    moodle_publicacion.falla_aviso = True
    res = client.post(f"/api/v1/refuerzos/{refuerzo['id']}/publicar", headers=sincronizado, json={"confirmado": True})
    assert res.status_code == 200, res.text
    assert res.json()["notificado"] is False
    assert repositories.get_refuerzo(refuerzo_id=refuerzo["id"])["estado"] == "PUBLICADO"
    logs = repositories.filas("logs_sistema")
    error = next(log for log in logs if log["tipo_proceso"] == "NOTIFICAR_REFUERZO")
    assert error["estado"] == "ERROR" and error["detalle"]["cmid"] == res.json()["cmid"]
    assert logs[-1]["tipo_proceso"] == "PUBLICAR_REFUERZO" and logs[-1]["detalle"]["notificado"] is False


def test_publicar_es_idempotente(sincronizado, moodle_publicacion):
    alerta = _alerta(sincronizado, "U-04")
    refuerzo = client.post(f"/api/v1/alertas/{alerta['id']}/atender", headers=sincronizado).json()["refuerzo"]
    primera = client.post(f"/api/v1/refuerzos/{refuerzo['id']}/publicar", headers=sincronizado, json={"confirmado": True})
    segunda = client.post(f"/api/v1/refuerzos/{refuerzo['id']}/publicar", headers=sincronizado, json={"confirmado": True})
    assert primera.json()["cmid"] == segunda.json()["cmid"]
    assert repositories.filas("logs_sistema")[-1]["detalle"]["ya_existia"] is True


def test_publicar_fallo_de_moodle_502_sin_cambiar_estado(sincronizado, moodle_publicacion):
    alerta = _alerta(sincronizado, "U-04")
    refuerzo = client.post(f"/api/v1/alertas/{alerta['id']}/atender", headers=sincronizado).json()["refuerzo"]
    moodle_publicacion.falla = True
    res = client.post(f"/api/v1/refuerzos/{refuerzo['id']}/publicar", headers=sincronizado, json={"confirmado": True})
    assert res.status_code == 502
    assert "no está matriculado" in res.json()["detail"]
    assert repositories.get_refuerzo(refuerzo_id=refuerzo["id"])["estado"] == "BORRADOR"
    assert repositories.get_refuerzo(refuerzo_id=refuerzo["id"])["cmid"] is None
    assert _alerta(sincronizado, "U-04")["estado"] == "ATENDIDA"
    log = repositories.filas("logs_sistema")[-1]
    assert log["tipo_proceso"] == "PUBLICAR_REFUERZO" and log["estado"] == "ERROR"


def test_publicar_alerta_cerrada_409(sincronizado, moodle_publicacion):
    alerta = _alerta(sincronizado, "U-04")
    refuerzo = client.post(f"/api/v1/alertas/{alerta['id']}/atender", headers=sincronizado).json()["refuerzo"]
    client.patch(f"/api/v1/alertas/{alerta['id']}/cerrar", headers=sincronizado)
    res = client.post(f"/api/v1/refuerzos/{refuerzo['id']}/publicar", headers=sincronizado, json={"confirmado": True})
    assert res.status_code == 409
    assert moodle_publicacion.llamadas == []


# =============================================================================== Reporte del curso
def test_reporte_del_curso(sincronizado):
    res = client.get("/api/v1/courses/2/reporte", headers=sincronizado)
    assert res.status_code == 200
    r = res.json()
    assert r["curso"]["shortname"] == "SOF-POO-A"
    assert r["periodo"]["codigo"] == settings.PERIODO_CODIGO
    assert r["fecha_sincronizacion"] == sync_service.SYNC_STATE["ultima_sincronizacion"]
    m = r["metricas"]
    assert m["total_estudiantes"] == 4
    assert (m["criticos"], m["en_riesgo"], m["aceptables"]) == (1, 1, 2)
    assert m["nota_minima"] == 2.65
    assert r["distribucion_estados"] == {
        "calificado": 18, "cero": 1, "sin_entrega": 1, "pendiente": 1, "total_registros": 21,
        "estudiantes_con_cero": 1, "estudiantes_sin_entrega": 1, "estudiantes_con_pendiente": 1,
    }
    assert (r["alertas"]["r1_activas"], r["alertas"]["r2_activas"]) == (1, 1)
    assert [p["id_number"] for p in r["estudiantes_prioritarios"]] == ["U-04", "U-11"]
    assert any("Carlos Andrés Mendoza Paredes (2.65)" in h for h in r["hallazgos"])
    assert any("descenso sostenido" in h and "Sebastián Alejandro Romero Haro" in h for h in r["hallazgos"])
    assert not any("R1" in t or "R2" in t for t in r["hallazgos"] + r["recomendaciones"])
    assert any("pendientes" in x for x in r["recomendaciones"])


def test_reporte_descargable_markdown(sincronizado):
    res = client.get("/api/v1/courses/2/reporte", params={"formato": "md"}, headers=sincronizado)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/markdown")
    assert 'attachment; filename="informe_SOF-POO-A.md"' == res.headers["content-disposition"]
    assert res.text.startswith("# Informe académico del curso")
    assert "| Asignatura | Programación orientada a objetos - Paralelo A (SOF-POO-A) |" in res.text
    assert "| Docente | Roberto Patricio Gómez Salazar |" in res.text and "| Sin entrega | 1 | 1 |" in res.text
    assert "## 1. Métricas del curso" in res.text and "## 5. Recomendaciones" in res.text
    # Sobrio: sin rellenos ni marcas de la herramienta
    assert "EduMonitor" not in res.text and "determinista" not in res.text and "—" not in res.text


def test_reporte_curso_ajeno_403_y_desconocido_404(sincronizado):
    assert client.get("/api/v1/courses/3/reporte", headers=sincronizado).status_code == 403
    assert client.get("/api/v1/courses/99/reporte", headers=sincronizado).status_code == 404


# =============================================================================== Chat del agente con herramientas
def _chat(headers, mensaje, **extra):
    res = client.post("/api/v1/agent/chat", headers=headers, json={"mensaje": mensaje, **extra})
    assert res.status_code == 200, res.text
    return res.json()


def test_chat_alertas_de_un_curso_con_herramienta_real(sincronizado):
    data = _chat(sincronizado, "¿Qué estudiantes de POO necesitan atención?")
    assert data["plan_fuente"] == "reglas_deterministas"     # agente IA inaccesible en pruebas
    usadas = {h["herramienta"]: h for h in data["herramientas"]}
    assert usadas["identificar_alertas"]["parametros"] == {"course_id": 2}
    assert {a["nombres"] for a in usadas["identificar_alertas"]["resultado"]["alertas"]} == \
           {"Carlos Andrés Mendoza Paredes", "Sebastián Alejandro Romero Haro"}
    assert "Carlos Andrés Mendoza Paredes" in data["respuesta"] and "Sebastián Alejandro Romero Haro" in data["respuesta"]

    logs = [log for log in repositories.filas("logs_sistema") if log["tipo_proceso"] == "AGENTE_HERRAMIENTA"]
    assert logs[-1]["detalle"]["herramienta"] == "identificar_alertas"
    assert logs[-1]["detalle"]["parametros"] == {"course_id": 2}
    assert logs[-1]["detalle"]["docente"] == "rgomez4824@uta.edu.ec"
    assert repositories.filas("logs_sistema")[-1]["tipo_proceso"] == "AGENTE_CHAT"


def test_chat_calificaciones_de_un_estudiante_sin_inventar_datos(sincronizado):
    data = _chat(sincronizado, "Dame las notas de Carlos Mendoza")
    llamada = next(h for h in data["herramientas"] if h["herramienta"] == "obtener_calificaciones")
    assert llamada["parametros"]["estudiante"] == "Carlos Andrés Mendoza Paredes"
    fila = llamada["resultado"]["calificaciones"][0]
    assert fila["nota_final"] == 2.65 and "U2-T4 SIN_ENTREGA" in fila["incidencias"]
    assert "2.65/10" in data["respuesta"] and "U2-T4 sin entrega" in data["respuesta"]


def test_chat_usa_al_menos_tres_herramientas_distintas(sincronizado):
    usadas = set()
    for mensaje in ("¿Qué cursos tengo?", "Hazme un resumen del curso SOF-POO-A",
                    "¿Hay alertas R2 en POO?", "notas de U-04"):
        usadas |= {h["herramienta"] for h in _chat(sincronizado, mensaje)["herramientas"]}
    assert len(usadas) >= 3
    assert usadas == {"listar_cursos_autorizados", "generar_resumen", "identificar_alertas", "obtener_calificaciones"}


def test_chat_no_expone_cursos_ajenos(sincronizado):
    data = _chat(sincronizado, "resumen", course_id=3)
    assert all("error" in h["resultado"] for h in data["herramientas"])
    assert "SOF-ED-B" not in data["respuesta"]
    log = [log for log in repositories.filas("logs_sistema") if log["tipo_proceso"] == "AGENTE_HERRAMIENTA"][-1]
    assert log["estado"] == "ADVERTENCIA"


def _agente_responde(monkeypatch, cuerpo):
    real = httpx.AsyncClient

    def handler(request):
        assert request.url.path == "/api/v1/chat/plan"
        return httpx.Response(200, json=cuerpo)

    monkeypatch.setattr(agente_herramientas.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


def test_chat_usa_el_plan_del_llm_cuando_es_valido(sincronizado, monkeypatch):
    _agente_responde(monkeypatch, {"fuente": "ollama_slm", "llamadas": [
        {"herramienta": "identificar_alertas", "parametros": {"course_id": 2, "regla": "R1"}}]})
    data = _chat(sincronizado, "alumnos con nota crítica en POO")
    assert data["plan_fuente"].startswith("ollama_slm")
    assert data["herramientas"][0]["herramienta"] == "identificar_alertas"
    assert data["herramientas"][0]["parametros"] == {"course_id": 2, "regla": "R1"}
    alertas = data["herramientas"][0]["resultado"]["alertas"]
    assert [a["nombres"] for a in alertas] == ["Carlos Andrés Mendoza Paredes"]


def test_entidades_mencionadas_prevalecen_sobre_el_llm(sincronizado, monkeypatch):
    # El modelo elige bien la herramienta pero mal el estudiante: manda lo que el docente escribió
    _agente_responde(monkeypatch, {"fuente": "ollama_slm", "llamadas": [
        {"herramienta": "obtener_calificaciones", "parametros": {"estudiante": "Camila Andrade"}}]})
    data = _chat(sincronizado, "Dame las notas de Carlos Mendoza en POO")
    llamada = data["herramientas"][0]
    assert llamada["parametros"] == {"course_id": 2, "estudiante": "Carlos Andrés Mendoza Paredes"}
    assert llamada["resultado"]["calificaciones"][0]["id_number"] == "U-04"


def test_plan_del_llm_se_complementa_con_la_intencion_explicita(sincronizado, monkeypatch):
    # El modelo sólo lista cursos, pero la pregunta pide alertas: se añade identificar_alertas
    _agente_responde(monkeypatch, {"fuente": "ollama_slm", "llamadas": [
        {"herramienta": "listar_cursos_autorizados", "parametros": {}}]})
    data = _chat(sincronizado, "¿Qué estudiantes necesitan atención en todas mis materias?")
    assert data["plan_fuente"] == "ollama_slm+reglas"
    assert [h["herramienta"] for h in data["herramientas"]] == ["listar_cursos_autorizados", "identificar_alertas"]


def test_si_nombra_una_materia_no_se_anexa_el_listado_de_cursos(sincronizado, monkeypatch):
    _agente_responde(monkeypatch, {"fuente": "ollama_slm", "llamadas": [
        {"herramienta": "listar_cursos_autorizados", "parametros": {}},
        {"herramienta": "generar_resumen", "parametros": {}}]})
    data = _chat(sincronizado, "¿Cómo va Programación orientada a objetos, paralelo A?")
    assert [(h["herramienta"], h["parametros"]) for h in data["herramientas"]] == [("generar_resumen", {"course_id": 2})]


@pytest.mark.parametrize("llamadas", [
    [{"herramienta": "borrar_base_de_datos", "parametros": {}}],                       # herramienta inexistente
    [{"herramienta": "obtener_calificaciones", "parametros": {"course_id": 3}}],       # curso de otro docente
    [{"herramienta": "generar_resumen", "parametros": {"course_id": "abc"}}],          # parámetro inválido
])
def test_chat_rechaza_planes_del_llm_invalidos(sincronizado, monkeypatch, llamadas):
    _agente_responde(monkeypatch, {"fuente": "ollama_slm", "llamadas": llamadas})
    data = _chat(sincronizado, "resumen de POO")
    assert data["plan_fuente"] == "reglas_deterministas"
    assert [h["herramienta"] for h in data["herramientas"]] == ["generar_resumen"]


def test_hallazgos_en_tres_bloques_y_recomendaciones_por_prioridad(sincronizado):
    r = client.get("/api/v1/courses/2/reporte", headers=sincronizado).json()
    grupos = r["hallazgos_grupos"]
    assert [g["titulo"] for g in grupos] == ["Rendimiento general del curso", "Estudiantes que requieren atención",
                                             "Componentes y entregas pendientes"]
    assert grupos[0]["items"][0].startswith("Promedio general ")
    assert any("Unidad 1" in h and "Unidad 2" in h for h in grupos[0]["items"])            # variación U1 -> U2
    assert grupos[1]["items"] == [
        "1 estudiante en nivel crítico: Carlos Andrés Mendoza Paredes (2.65).",
        "1 estudiante con descenso sostenido entre unidades: Sebastián Alejandro Romero Haro."]
    assert grupos[2]["items"][0].startswith("El componente con menor promedio es ")
    assert grupos[2]["items"][-1] == ("1 actividad sigue pendiente de calificación (1 estudiante); no cuenta en el "
                                      "promedio.")
    assert r["hallazgos"] == [h for g in grupos for h in g["items"]]
    # Prioridad académica: críticos, descenso, componente débil, entregas faltantes y pendientes
    prefijos = ["Atención inmediata", "Seguimiento al descenso", "Refuerzo del componente", "Gestión de entregas",
                "Calificación de pendientes"]
    orden = [next(i for i, p in enumerate(prefijos) if x.startswith(p)) for x in r["recomendaciones"]]
    assert orden == sorted(orden) and orden[0] == 0
    assert all(x.split(": ", 1)[1][:1].islower() for x in r["recomendaciones"] if ": " in x)   # minúscula tras «:»
    # Concordancia natural: nada de «estudiante(s)», «registro(s)» ni «actividad(es)»
    assert not any("(s)" in t or "(es)" in t for t in r["hallazgos"] + r["recomendaciones"])


def test_markdown_con_subbloques_y_recomendaciones_numeradas(sincronizado):
    md = client.get("/api/v1/courses/2/reporte", params={"formato": "md"}, headers=sincronizado).text
    assert "### 4.1. Rendimiento general del curso" in md and "### 4.2. Estudiantes que requieren atención" in md
    assert "### 4.3. Componentes y entregas pendientes" in md
    assert "\n1. Atención inmediata a 1 estudiante crítico:" in md and "\n2. Seguimiento al descenso sostenido" in md
    assert "(s)" not in md and "(es)" not in md


def test_plural_concuerda_con_la_cantidad():
    from app.services.reporte_service import plural
    assert plural(1, "estudiante", "estudiantes") == "1 estudiante"
    assert plural(2, "registro", "registros") == "2 registros"
    assert plural(0, "actividad sigue pendiente", "actividades siguen pendientes") == "0 actividades siguen pendientes"
