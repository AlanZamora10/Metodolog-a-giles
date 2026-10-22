from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


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


def test_courses_summary_endpoint():
    response = client.get("/api/v1/courses/MAT1/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["materia_codigo"] == "MAT1"
    assert data["total_estudiantes"] == 7
    assert data["estudiantes_criticos"] >= 2


def test_student_detail_endpoint():
    response = client.get("/api/v1/students/U-05")
    assert response.status_code == 200
    data = response.json()
    assert data["id_number"] == "U-05"
    assert data["nota_final"] == 3.50
    assert data["nivel_riesgo"] == "CRITICO"


def test_logs_endpoint():
    response = client.get("/api/v1/logs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
