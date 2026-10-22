from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_login_docente_success():
    """Verifica inicio de sesión exitoso como DOCENTE."""
    res = client.post("/api/v1/auth/login", json={
        "email": "docente@uta.edu.ec",
        "password": "Docente2026!"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["rol"] == "DOCENTE"
    assert "Hernán Naranjo" in data["user"]["nombres"]


def test_login_estudiante_success():
    """Verifica inicio de sesión exitoso como ESTUDIANTE."""
    res = client.post("/api/v1/auth/login", json={
        "email": "estudiante.c@uta.edu.ec",
        "password": "Estudiante2026!"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["rol"] == "ESTUDIANTE"
    assert data["user"]["id_number"] == "U-05"


def test_login_invalid_password():
    """Verifica rechazo con HTTP 401 para credenciales inválidas."""
    res = client.post("/api/v1/auth/login", json={
        "email": "docente@uta.edu.ec",
        "password": "WrongPassword!"
    })
    assert res.status_code == 401
    assert "Credenciales incorrectas" in res.json()["detail"]


def test_register_new_docente():
    """Verifica creación de nueva cuenta con rol DOCENTE."""
    res = client.post("/api/v1/auth/register", json={
        "nombres": "Ing. Carlos Perez, Mg.",
        "email": "carlos.perez@uta.edu.ec",
        "password": "Password123!",
        "rol": "DOCENTE"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["user"]["rol"] == "DOCENTE"
    assert data["user"]["email"] == "carlos.perez@uta.edu.ec"
    assert "access_token" in data


def test_register_new_estudiante():
    """Verifica creación de nueva cuenta con rol ESTUDIANTE."""
    res = client.post("/api/v1/auth/register", json={
        "nombres": "Estudiante H",
        "email": "estudiante.h@uta.edu.ec",
        "password": "Password123!",
        "rol": "ESTUDIANTE",
        "id_number": "U-10"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["user"]["rol"] == "ESTUDIANTE"
    assert data["user"]["id_number"] == "U-10"


def test_register_duplicate_email_fails():
    """Verifica que no se permita registrar un correo duplicado."""
    res = client.post("/api/v1/auth/register", json={
        "nombres": "Docente Duplicado",
        "email": "docente@uta.edu.ec",
        "password": "Password123!",
        "rol": "DOCENTE"
    })
    assert res.status_code == 400
    assert "ya se encuentra registrado" in res.json()["detail"]


def test_auth_me_protected_endpoint():
    """Verifica acceso a perfil autenticado mediante Bearer Token (HU-14)."""
    # 1. Login para obtener token
    login_res = client.post("/api/v1/auth/login", json={
        "email": "docente@uta.edu.ec",
        "password": "Docente2026!"
    })
    token = login_res.json()["access_token"]

    # 2. Consulta con token válido
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "docente@uta.edu.ec"
    assert me_res.json()["rol"] == "DOCENTE"

    # 3. Consulta sin token (falla 401)
    unauth_res = client.get("/api/v1/auth/me")
    assert unauth_res.status_code == 401
