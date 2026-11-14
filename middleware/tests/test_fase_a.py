"""
Fase A — SQL Server, publicación real en Moodle, reporte del curso y chat del agente con herramientas.

Moodle se simula (sincronización, login y local_edumonitor_crear_tarea); la base es SQLite en memoria
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
    assert len(ddl) == 12
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
    falla = False

    def __init__(self):
        pass

    async def crear_tarea_refuerzo(self, **kw):
        if FakeMoodlePublicacion.falla:
            raise MoodleError("local_edumonitor_crear_tarea: El estudiante no está matriculado (activo) en el curso.")
        existente = any(llamada["codigo"] == kw["codigo"] for llamada in FakeMoodlePublicacion.llamadas)
        FakeMoodlePublicacion.llamadas.append(kw)
        cmid = 700 + int(kw["codigo"].split("-")[1])
        return {"cmid": cmid, "url": f"http://localhost:8080/mod/assign/view.php?id={cmid}", "seccion": 4,
                "existente": existente}


@pytest.fixture
def moodle_publicacion(monkeypatch):
    FakeMoodlePublicacion.llamadas, FakeMoodlePublicacion.falla = [], False
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
    assert llamada["email_estudiante"] == "dcurillo@uta.edu.ec"   # visible sólo para ese estudiante
    assert llamada["nombre"] == "Refuerzo Tareas U2"
    assert llamada["codigo"] == f"REF-{refuerzo['id']}"
    assert llamada["fecha_entrega"] == int(datetime(2099, 1, 16, 4, 59, tzinfo=timezone.utc).timestamp())

    guardado = repositories.get_refuerzo(refuerzo_id=refuerzo["id"])
    assert guardado["estado"] == "PUBLICADO" and guardado["cmid"] == data["cmid"]
    assert guardado["moodle_url"] == data["moodle_link"]
    assert _alerta(sincronizado, "U-04")["estado"] == "PUBLICADO"
    log = repositories.filas("logs_sistema")[-1]
    assert log["tipo_proceso"] == "PUBLICAR_REFUERZO" and log["estado"] == "EXITO" and log["detalle"]["cmid"] == data["cmid"]


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
    assert any("Diego Curillo (2.65)" in h for h in r["hallazgos"])
    assert any("R2" in h and "Sebastián Romero" in h for h in r["hallazgos"])
    assert any("pendientes" in x for x in r["recomendaciones"])


def test_reporte_descargable_markdown(sincronizado):
    res = client.get("/api/v1/courses/2/reporte", params={"formato": "md"}, headers=sincronizado)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/markdown")
    assert 'attachment; filename="informe_SOF-POO-A.md"' == res.headers["content-disposition"]
    assert "# Informe del curso SOF-POO-A" in res.text and "| Sin entrega | 1 | 1 |" in res.text


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
           {"Diego Curillo", "Sebastián Romero"}
    assert "Diego Curillo" in data["respuesta"] and "Sebastián Romero" in data["respuesta"]

    logs = [log for log in repositories.filas("logs_sistema") if log["tipo_proceso"] == "AGENTE_HERRAMIENTA"]
    assert logs[-1]["detalle"]["herramienta"] == "identificar_alertas"
    assert logs[-1]["detalle"]["parametros"] == {"course_id": 2}
    assert logs[-1]["detalle"]["docente"] == "rgomez@uta.edu.ec"
    assert repositories.filas("logs_sistema")[-1]["tipo_proceso"] == "AGENTE_CHAT"


def test_chat_calificaciones_de_un_estudiante_sin_inventar_datos(sincronizado):
    data = _chat(sincronizado, "Dame las notas de Diego Curillo")
    llamada = next(h for h in data["herramientas"] if h["herramienta"] == "obtener_calificaciones")
    assert llamada["parametros"]["estudiante"] == "Diego Curillo"
    fila = llamada["resultado"]["calificaciones"][0]
    assert fila["nota_final"] == 2.65 and "U2-T4 SIN_ENTREGA" in fila["incidencias"]
    assert "2.65/10" in data["respuesta"] and "U2-T4 (sin entrega)" in data["respuesta"]


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
    assert [a["nombres"] for a in alertas] == ["Diego Curillo"]


def test_entidades_mencionadas_prevalecen_sobre_el_llm(sincronizado, monkeypatch):
    # El modelo elige bien la herramienta pero mal el estudiante: manda lo que el docente escribió
    _agente_responde(monkeypatch, {"fuente": "ollama_slm", "llamadas": [
        {"herramienta": "obtener_calificaciones", "parametros": {"estudiante": "Camila Andrade"}}]})
    data = _chat(sincronizado, "Dame las notas de Diego Curillo en POO")
    llamada = data["herramientas"][0]
    assert llamada["parametros"] == {"course_id": 2, "estudiante": "Diego Curillo"}
    assert llamada["resultado"]["calificaciones"][0]["id_number"] == "U-04"


def test_plan_del_llm_se_complementa_con_la_intencion_explicita(sincronizado, monkeypatch):
    # El modelo sólo lista cursos, pero la pregunta pide alertas: se añade identificar_alertas
    _agente_responde(monkeypatch, {"fuente": "ollama_slm", "llamadas": [
        {"herramienta": "listar_cursos_autorizados", "parametros": {}}]})
    data = _chat(sincronizado, "¿Qué estudiantes de POO necesitan atención?")
    assert data["plan_fuente"] == "ollama_slm+reglas"
    assert [h["herramienta"] for h in data["herramientas"]] == ["listar_cursos_autorizados", "identificar_alertas"]


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
