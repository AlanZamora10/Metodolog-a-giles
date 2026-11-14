import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import sync_service

client = TestClient(app)


def _auth_docente():
    res = client.post("/api/v1/auth/login", json={"email": "rgomez@uta.edu.ec", "password": "Docente2026!"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture(autouse=True)
def sin_sincronizacion():
    """Sin cursos sincronizados, courses/students responden con el dataset heredado de HU-01 (MAT1)."""
    sync_service.SYNC_STATE.update({"ultima_sincronizacion": None, "moodle": None, "cursos": []})
    yield


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "FISEI" in data["institucion"]
    assert "Sprint 1" in data["sprint"]


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "moodle_status" in data
    # SQLite en memoria en pruebas unitarias; el motor de TEST_DATABASE_URL (mssql / postgresql) si se define
    url = os.environ.get("TEST_DATABASE_URL", "")
    esperado = "mssql" if url.startswith("mssql") else "postgresql" if url else "sqlite"
    assert data["persistencia"].startswith(esperado)


def test_courses_summary_endpoint():
    response = client.get("/api/v1/courses/MAT1/summary", headers=_auth_docente())
    assert response.status_code == 200
    data = response.json()
    assert data["materia_codigo"] == "MAT1"
    assert data["total_estudiantes"] == 7
    assert data["estudiantes_criticos"] >= 2


def test_student_detail_endpoint():
    response = client.get("/api/v1/students/U-05", headers=_auth_docente())
    assert response.status_code == 200
    data = response.json()
    assert data["id_number"] == "U-05"
    assert data["nota_final"] == 3.50
    assert data["nivel_riesgo"] == "CRITICO"


def test_logs_endpoint():
    response = client.get("/api/v1/logs", headers=_auth_docente())
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
