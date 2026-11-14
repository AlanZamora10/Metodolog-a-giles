"""
Sprint 3 — Persistencia real de la sincronización, usuarios y auditoría.

Se inyecta un motor SQLite en memoria (mismo esquema que PostgreSQL vía app.database) para
verificar los UPSERT, la idempotencia y que los datos sobreviven a un reinicio del middleware.
"""

import pytest
from fastapi.testclient import TestClient

from app import database, repositories
from app.main import app
from app.services import sync_service
from moodle_fake import DOCENTE, FakeMoodleSprint3

client = TestClient(app)


@pytest.fixture
def motor(monkeypatch):
    engine = database.new_sqlite_engine()
    database.use_engine(engine, "sqlite_prueba")
    sync_service.SYNC_STATE.update({"ultima_sincronizacion": None, "moodle": None, "cursos": []})
    monkeypatch.setattr(sync_service, "MoodleClient", lambda: FakeMoodleSprint3())
    yield engine


def _auth(creds=DOCENTE):
    res = client.post("/api/v1/auth/login", json=creds)
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _sincronizar(headers):
    res = client.post("/api/sincronizacion", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _conteos(engine):
    tablas = ("materias", "estudiantes", "periodos", "parciales", "categorias_unidad", "actividades",
              "calificaciones", "calificaciones_ponderadas", "alertas_tempranas")
    return {t: repositories.contar(t, engine) for t in tablas}


def test_esquema_contiene_las_12_tablas(motor):
    from sqlalchemy import inspect
    tablas = set(inspect(motor).get_table_names())
    assert {"usuarios", "materias", "periodos", "parciales", "estudiantes", "categorias_unidad", "actividades",
            "calificaciones", "calificaciones_ponderadas", "logs_sistema", "alertas_tempranas",
            "refuerzos"} <= tablas


def test_sincronizacion_persiste_en_todas_las_tablas(motor):
    data = _sincronizar(_auth())
    assert data["persistencia"]["motor"] == "sqlite_prueba"
    assert _conteos(motor) == {
        "materias": 2, "estudiantes": 4, "periodos": 1, "parciales": 2, "categorias_unidad": 4,
        "actividades": 16, "calificaciones": 42, "calificaciones_ponderadas": 8, "alertas_tempranas": 4,
    }

    materia = next(m for m in repositories.filas("materias", motor) if m["codigo"] == "SOF-POO-A")
    assert materia["moodle_course_id"] == 2
    assert materia["docentes"] == ["rgomez@uta.edu.ec"]

    actividades = {a["id"]: a for a in repositories.filas("actividades", motor)}
    notas = {
        actividades[c["actividad_id"]]["id_number_normalizado"]: c
        for c in repositories.filas("calificaciones", motor)
        if actividades[c["actividad_id"]]["materia_id"] == materia["id"]
        and c["estudiante_id"] in {e["id"] for e in repositories.filas("estudiantes", motor) if e["id_number"] == "U-04"}
    }
    assert notas["SOF-POO-A-U2-T4"]["estado"] == "SIN_ENTREGA"
    assert notas["SOF-POO-A-U2-T4"]["entregado"] is False and notas["SOF-POO-A-U2-T4"]["nota"] == 0.0
    assert notas["SOF-POO-A-U1-T2"]["nota"] == 0.0 and notas["SOF-POO-A-U1-T2"]["estado"] == "CALIFICADO"
    assert actividades[next(iter(
        a["id"] for a in actividades.values() if a["id_number_normalizado"] == "SOF-POO-A-U1-A1"))][
        "tipo_componente"] == "AUTONOMO"

    ponderada = next(
        p for p in repositories.filas("calificaciones_ponderadas", motor)
        if p["materia_id"] == materia["id"] and p["nivel_riesgo"] == "CRITICO"
    )
    assert ponderada["nota_final"] == 2.65


def test_pendiente_se_guarda_sin_nota(motor):
    _sincronizar(_auth())
    pendientes = [c for c in repositories.filas("calificaciones", motor) if c["estado"] == "PENDIENTE"]
    assert len(pendientes) == 2  # U-09 en los dos cursos
    assert all(c["nota"] is None for c in pendientes)


def test_sincronizacion_es_idempotente(motor):
    headers = _auth()
    _sincronizar(headers)
    primera = _conteos(motor)
    _sincronizar(headers)
    assert _conteos(motor) == primera


def test_auditoria_en_logs_sistema(motor):
    headers = _auth()
    _sincronizar(headers)
    logs = repositories.filas("logs_sistema", motor)
    assert any(log["tipo_proceso"] == "INICIO_SERVICIO" for log in logs)
    sync_log = [log for log in logs if log["tipo_proceso"] == "SINCRONIZACION"][-1]
    assert sync_log["estado"] == "EXITO"
    assert sync_log["detalle"]["persistencia"]["alertas"]["creadas"] == 4
    assert sync_log["tiempo_ejecucion_ms"] is not None

    # GET /api/v1/logs lee desde la base
    api_logs = client.get("/api/v1/logs", headers=headers).json()
    assert api_logs[-1]["id"] == sync_log["id"]
    assert api_logs[-1]["tipo_proceso"] == "SINCRONIZACION"


def test_datos_sobreviven_a_reinicio(motor):
    headers = _auth()
    _sincronizar(headers)
    antes = client.get("/api/cursos/2/estudiantes", headers=headers).json()

    # Simula `docker compose restart middleware`: memoria vacía, misma base
    sync_service.SYNC_STATE.update({"ultima_sincronizacion": None, "moodle": None, "cursos": []})
    database.use_engine(motor, "sqlite_prueba")

    despues = client.get("/api/cursos/2/estudiantes", headers=headers)
    assert despues.status_code == 200
    despues = despues.json()
    assert despues["promedio"] == antes["promedio"]
    assert [(e["id_number"], e["nota_final"], e["nivel_riesgo"], e["estados"]) for e in despues["estudiantes"]] == \
           [(e["id_number"], e["nota_final"], e["nivel_riesgo"], e["estados"]) for e in antes["estudiantes"]]
    assert sync_service.SYNC_STATE["moodle"] == {"sitio": "Moodle UTA", "version": "4.3.2"}
    assert client.get("/api/sincronizacion", headers=headers).json()["total_cursos"] == 1


def test_login_moodle_guarda_perfil_sin_contrasena_local(motor):
    assert client.post("/api/v1/auth/login", json=DOCENTE).status_code == 200
    fila = repositories.user_by_email("rgomez@uta.edu.ec", motor)
    assert fila["rol"] == "DOCENTE" and fila["nombres"] == "Ing. Roberto Gómez"
    assert fila["password_hash"] == "MOODLE"          # la contraseña sólo vive en Moodle
    assert fila["moodle_user_id"] == 10 and fila["moodle_username"] == "rgomez"
    primer_acceso = fila["ultimo_acceso"]

    # Un segundo login (ahora con el usuario de Moodle) actualiza el mismo perfil, no lo duplica
    assert client.post("/api/v1/auth/login", json={"email": "rgomez", "password": "Docente2026!"}).status_code == 200
    assert repositories.contar("usuarios", motor) == 1
    assert repositories.user_by_email("rgomez@uta.edu.ec", motor)["ultimo_acceso"] >= primer_acceso
    logs = [log for log in repositories.filas("logs_sistema", motor) if log["tipo_proceso"] == "LOGIN"]
    assert len(logs) == 2 and all(log["estado"] == "EXITO" for log in logs)


def test_fallo_de_persistencia_no_impide_sincronizar(motor, monkeypatch):
    def falla(*_a, **_k):
        raise RuntimeError("base no disponible")

    monkeypatch.setattr(repositories, "persist_sync", falla)
    data = _sincronizar(_auth())
    assert data["total_cursos"] == 1
    assert "error" in data["persistencia"]
    assert repositories.filas("logs_sistema", motor)[-1]["estado"] == "ADVERTENCIA"
