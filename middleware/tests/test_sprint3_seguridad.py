"""
Sprint 3 — Seguridad JWT en todos los endpoints de datos.

  - 401 sin token o con token inválido/expirado.
  - 403 para roles distintos de DOCENTE.
  - 403 cuando el docente intenta operar sobre alertas de un curso que no dicta en Moodle.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.services import sync_service
from app.services.auth_service import create_access_token
from moodle_fake import DOCENTE, OTRO_DOCENTE, FakeMoodleSprint3, token_con_rol

client = TestClient(app)

PROTEGIDOS = [
    ("get", "/api/v1/alertas"),
    ("get", "/api/v1/alertas/1"),
    ("post", "/api/v1/alertas/1/atender"),
    ("patch", "/api/v1/alertas/1/cerrar"),
    ("post", "/api/v1/refuerzos/1/publicar"),
    ("get", "/api/v1/students"),
    ("get", "/api/v1/students/U-05"),
    ("get", "/api/v1/courses"),
    ("get", "/api/v1/courses/MAT1/summary"),
    ("get", "/api/v1/logs"),
    ("get", "/api/v1/alerts"),
    ("post", "/api/v1/sincronizacion"),
    ("get", "/api/cursos/2/estudiantes"),
    ("get", "/api/v1/courses/2/reporte"),
    ("post", "/api/v1/agent/chat"),
    ("get", "/api/v1/agent/herramientas"),
]


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    database.use_engine(database.new_sqlite_engine(), "sqlite_prueba")
    sync_service.SYNC_STATE.update({"ultima_sincronizacion": None, "moodle": None, "cursos": []})
    monkeypatch.setattr(sync_service, "MoodleClient", lambda: FakeMoodleSprint3())
    yield


def _llamar(metodo, ruta, headers=None):
    kwargs = {"headers": headers or {}}
    if ruta.endswith("/publicar"):
        kwargs["json"] = {"confirmado": True}
    if ruta.endswith("/chat"):
        kwargs["json"] = {"mensaje": "resumen"}
    return getattr(client, metodo)(ruta, **kwargs)


def _auth(creds):
    res = client.post("/api/v1/auth/login", json=creds)
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.mark.parametrize("metodo,ruta", PROTEGIDOS)
def test_sin_token_401(metodo, ruta):
    res = _llamar(metodo, ruta)
    assert res.status_code == 401
    assert res.headers.get("www-authenticate") == "Bearer"


@pytest.mark.parametrize("metodo,ruta", PROTEGIDOS)
def test_token_invalido_401(metodo, ruta):
    assert _llamar(metodo, ruta, {"Authorization": "Bearer token.falso.123"}).status_code == 401


def test_token_expirado_401():
    vencido = create_access_token({"sub": DOCENTE["email"], "rol": "DOCENTE"}, expires_delta=timedelta(seconds=-5))
    assert client.get("/api/v1/alertas", headers={"Authorization": f"Bearer {vencido}"}).status_code == 401


@pytest.mark.parametrize("metodo,ruta", PROTEGIDOS)
def test_rol_estudiante_403(metodo, ruta):
    assert _llamar(metodo, ruta, token_con_rol("ESTUDIANTE")).status_code == 403


def test_endpoints_publicos_siguen_abiertos():
    assert client.get("/").status_code == 200
    assert client.get("/api/v1/health").status_code == 200


def test_docente_no_opera_alertas_de_curso_ajeno():
    docente = _auth(DOCENTE)
    otro = _auth(OTRO_DOCENTE)
    client.post("/api/sincronizacion", headers=docente)

    propias = client.get("/api/v1/alertas", headers=docente).json()
    ajenas = client.get("/api/v1/alertas", headers=otro).json()
    assert {a["curso_codigo"] for a in propias} == {"SOF-POO-A"}
    assert {a["curso_codigo"] for a in ajenas} == {"SOF-ED-B"}

    alerta_ajena = ajenas[0]["id"]
    assert client.get(f"/api/v1/alertas/{alerta_ajena}", headers=docente).status_code == 403
    assert client.post(f"/api/v1/alertas/{alerta_ajena}/atender", headers=docente).status_code == 403
    assert client.patch(f"/api/v1/alertas/{alerta_ajena}/cerrar", headers=docente).status_code == 403
    assert client.get("/api/v1/courses/SOF-ED-B/summary", headers=docente).status_code == 403
    assert client.get("/api/v1/alertas/99999", headers=docente).status_code == 404
