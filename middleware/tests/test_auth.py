"""
Login unificado con Moodle (Fase A): el docente entra con su correo institucional de Moodle y la contraseña
de Moodle. EduMonitor valida contra Moodle (simulado en pruebas, ver tests/moodle_fake.py).
"""

from fastapi.testclient import TestClient

from app.main import app
from moodle_fake import FakeMoodleAuth

client = TestClient(app)


def _login(email, password):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_login_docente_con_correo_de_moodle():
    res = _login("rgomez4824@uta.edu.ec", "RobertoGomez1!")
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data and data["token_type"] == "bearer"
    assert data["user"]["rol"] == "DOCENTE"
    assert data["user"]["email"] == "rgomez4824@uta.edu.ec"
    assert "Roberto Patricio Gómez Salazar" == data["user"]["nombres"]
    assert data["user"]["id_number"] == "U-01"


def test_login_exige_correo_institucional_completo():
    # Sólo el correo institucional completo (@uta.edu.ec): ni el nombre de usuario ni otros dominios
    for identificador in ("rgomez", "rgomez4824", "rgomez4824@gmail.com"):
        res = _login(identificador, "RobertoGomez1!")
        assert res.status_code == 422, identificador
        assert "correo institucional" in res.json()["detail"]


def test_login_devuelve_la_cedula_del_docente():
    assert _login("rgomez4824@uta.edu.ec", "RobertoGomez1!").json()["user"]["cedula"] == "1803454824"


def test_login_correo_mayusculas_y_espacios():
    assert _login("  RGomez4824@UTA.edu.ec ", "RobertoGomez1!").status_code == 200


def test_login_contrasena_incorrecta_401():
    res = _login("rgomez4824@uta.edu.ec", "WrongPassword!")
    assert res.status_code == 401
    assert "Credenciales inválidas" in res.json()["detail"]


def test_login_usuario_inexistente_401():
    assert _login("nadie@uta.edu.ec", "RobertoGomez1!").status_code == 401


def test_cuenta_generica_ya_no_existe():
    # docente@uta.edu.ec dejó de ser una credencial válida: el docente usa su correo real de Moodle
    assert _login("docente@uta.edu.ec", "RobertoGomez1!").status_code == 401


def test_estudiante_de_moodle_no_accede_403():
    res = _login("cmendoza3199@uta.edu.ec", "CarlosMendoza1!")
    assert res.status_code == 403
    assert "exclusivo para docentes" in res.json()["detail"]


def test_moodle_caido_503():
    FakeMoodleAuth.caido = True
    res = _login("rgomez4824@uta.edu.ec", "RobertoGomez1!")
    assert res.status_code == 503
    assert "Moodle" in res.json()["detail"]


def test_registro_local_eliminado():
    res = client.post("/api/v1/auth/register", json={
        "nombres": "Ing. Carlos Perez", "email": "carlos.perez@uta.edu.ec", "password": "Password123!", "rol": "DOCENTE"})
    assert res.status_code in (404, 405)


def test_me_con_token_de_moodle():
    token = _login("rgomez4824@uta.edu.ec", "RobertoGomez1!").json()["access_token"]
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "rgomez4824@uta.edu.ec"
