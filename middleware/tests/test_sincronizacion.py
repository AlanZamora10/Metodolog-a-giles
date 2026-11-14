"""
Pruebas de la sincronización con Moodle UTA (Fase 2):
  - Login del docente y restricción de rol.
  - Restricción 403 por curso (el docente sólo ve los cursos donde es profesor en Moodle).
  - Cálculo de notas ponderadas 40/30/30 con SIN_ENTREGA y PENDIENTE.
  - Uso de MOODLE_URL / MOODLE_HOST_HEADER / MOODLE_TOKEN en el cliente HTTP.
Moodle se simula con un cliente falso, por lo que no requiere contenedores.
"""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import moodle_client as moodle_module
from app.services import sync_service
from app.services.moodle_client import MoodleClient, MoodleError
from moodle_fake import token_con_rol

client = TestClient(app)

DOCENTE = {"email": "rgomez@uta.edu.ec", "password": "Docente2026!"}


def _gi(idnumber: str, raw=None, feedback="", grademax=10):
    return {"idnumber": idnumber, "itemname": idnumber, "graderaw": raw, "grademax": grademax, "feedback": feedback}


class FakeMoodle:
    """Moodle simulado: curso 2 dictado por el docente, curso 3 por otro profesor."""

    def __init__(self, fail: bool = False):
        self.fail = fail

    async def call(self, wsfunction, **params):
        if self.fail:
            raise MoodleError("Moodle respondió HTTP 403")
        assert wsfunction == "core_webservice_get_site_info"
        return {"sitename": "Moodle UTA", "release": "4.3.2"}

    async def get_courses(self):
        return [
            {"id": 2, "shortname": "SOF-MA-B", "idnumber": "SOF-MA-B", "fullname": "(SOF) METODOLOGIAS AGILES - B"},
            {"id": 3, "shortname": "SOF-ED-B", "idnumber": "SOF-ED-B", "fullname": "(SOF) ESTRUCTURA DE DATOS - B"},
            {"id": 9, "shortname": "OTRO", "idnumber": "OTRO", "fullname": "Curso fuera del portafolio"},
        ]

    async def get_enrolled_users(self, course_id):
        profesor = "rgomez@uta.edu.ec" if course_id == 2 else "otro.docente@uta.edu.ec"
        return [
            {"id": 10, "fullname": "Profesor", "email": profesor, "roles": [{"shortname": "editingteacher"}]},
            {"id": 11, "fullname": "Estudiante A", "email": "estudiante.a@uta.edu.ec", "idnumber": "U-03",
             "roles": [{"shortname": "student"}]},
            {"id": 12, "fullname": "Estudiante F", "email": "estudiante.f@uta.edu.ec", "idnumber": "U-08",
             "roles": [{"shortname": "student"}]},
            {"id": 13, "fullname": "Estudiante G", "email": "estudiante.g@uta.edu.ec", "idnumber": "U-09",
             "roles": [{"shortname": "student"}]},
        ]

    async def get_grade_items(self, course_id):
        return [
            # Ítems de otros esquemas (categorías, total, supletorio) se ignoran
            {"userid": 11, "gradeitems": [_gi("U1-A1", 8.0), _gi("U1-T1", 80, grademax=100), _gi("U1-P1", 8.0),
                                          _gi("CAT-ACD", 8.0), _gi("SUP-1"), _gi("U3-A3")]},
            # ACD (7+6)/2=6.5 | Tareas (6+0 SIN ENTREGA)/2=3.0 | PAE 6.0
            {"userid": 12, "gradeitems": [_gi("U1-A1", 7.0), _gi("U2-A2", 6.0), _gi("U1-T1", 6.0),
                                          _gi("U2-T4", 0, "SIN ENTREGA"), _gi("U1-P1", 6.0)]},
            # PAE pendiente: sólo cuenta U1-P1
            {"userid": 13, "gradeitems": [_gi("U1-A1", 8.5), _gi("U1-T1", 8.0), _gi("U1-P1", 7.0),
                                          _gi("U2-P3", None, "PENDIENTE DE REVISIÓN")]},
        ]


def _token(creds) -> str:
    res = client.post("/api/v1/auth/login", json=creds)
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _auth(creds):
    return {"Authorization": f"Bearer {_token(creds)}"}


@pytest.fixture(autouse=True)
def fake_moodle(monkeypatch):
    monkeypatch.setattr(sync_service, "MoodleClient", lambda: FakeMoodle())
    sync_service.SYNC_STATE.update({"ultima_sincronizacion": None, "moodle": None, "cursos": []})
    yield


# ---------------------------------------------------------------- Login
def test_login_docente_devuelve_token_y_rol():
    res = client.post("/api/v1/auth/login", json=DOCENTE)
    assert res.status_code == 200
    assert res.json()["user"]["rol"] == "DOCENTE"


def test_login_credenciales_invalidas_401():
    res = client.post("/api/v1/auth/login", json={"email": DOCENTE["email"], "password": "mala"})
    assert res.status_code == 401


def test_sincronizacion_sin_token_401():
    assert client.post("/api/sincronizacion").status_code == 401


def test_sincronizacion_rol_estudiante_403():
    assert client.post("/api/sincronizacion", headers=token_con_rol("ESTUDIANTE")).status_code == 403


# ---------------------------------------------------------------- Sincronización
def test_sincronizacion_docente_solo_ve_sus_cursos():
    res = client.post("/api/sincronizacion", headers=_auth(DOCENTE))
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["moodle"]["sitio"] == "Moodle UTA"
    # Sólo SOF-MA-B: SOF-ED-B es de otro docente y OTRO no tiene el prefijo SOF-
    assert [c["shortname"] for c in data["cursos"]] == ["SOF-MA-B"]
    assert data["total_estudiantes"] == 3
    assert {e["id_number"] for e in data["estudiantes"]} == {"U-03", "U-08", "U-09"}


def test_sincronizacion_moodle_caido_502(monkeypatch):
    monkeypatch.setattr(sync_service, "MoodleClient", lambda: FakeMoodle(fail=True))
    res = client.post("/api/sincronizacion", headers=_auth(DOCENTE))
    assert res.status_code == 502
    assert "403" in res.json()["detail"]


# ---------------------------------------------------------------- Restricción 403 por curso
def test_curso_propio_200():
    headers = _auth(DOCENTE)
    client.post("/api/sincronizacion", headers=headers)
    res = client.get("/api/cursos/2/estudiantes", headers=headers)
    assert res.status_code == 200
    assert res.json()["total_estudiantes"] == 3


def test_curso_ajeno_403():
    headers = _auth(DOCENTE)
    client.post("/api/sincronizacion", headers=headers)
    res = client.get("/api/cursos/3/estudiantes", headers=headers)
    assert res.status_code == 403


def test_curso_no_sincronizado_404():
    res = client.get("/api/cursos/2/estudiantes", headers=_auth(DOCENTE))
    assert res.status_code == 404


# ---------------------------------------------------------------- Cálculo de notas
def test_calculo_notas_ponderadas_40_30_30():
    headers = _auth(DOCENTE)
    client.post("/api/sincronizacion", headers=headers)
    est = {e["id_number"]: e for e in client.get("/api/cursos/2/estudiantes", headers=headers).json()["estudiantes"]}

    assert est["U-03"]["nota_final"] == 8.00
    assert est["U-03"]["nivel_riesgo"] == "ACEPTABLE"

    # Escala 0-100 se normaliza a 10; ítems no Ux-[ATP]y y no evaluados se ignoran
    assert est["U-03"]["tareas"] == 8.0
    assert {a["id_number"] for a in est["U-03"]["actividades"]} == {"U1-A1", "U1-T1", "U1-P1"}

    # SIN ENTREGA cuenta 0: 0.4*6.5 + 0.3*3.0 + 0.3*6.0 = 5.30
    assert est["U-08"]["acd"] == 6.5
    assert est["U-08"]["tareas"] == 3.0
    assert est["U-08"]["estados"]["TAREAS"] == "SIN_ENTREGA"
    assert est["U-08"]["nota_final"] == 5.30
    assert est["U-08"]["nivel_riesgo"] == "EN_RIESGO"

    # PENDIENTE no cuenta: 0.4*8.5 + 0.3*8.0 + 0.3*7.0 = 7.90
    assert est["U-09"]["estados"]["PAE"] == "PENDIENTE"
    assert est["U-09"]["pae"] == 7.0
    assert est["U-09"]["nota_final"] == 7.90
    assert est["U-09"]["nivel_riesgo"] == "ACEPTABLE"


def test_calculo_nota_critica_con_cero():
    e = sync_service.construir_estudiante(
        {"id": 1, "fullname": "Diego Curillo", "idnumber": "U-04", "roles": [{"shortname": "student"}]},
        [_gi("U1-A1", 3.0), _gi("U1-T1", 4.0), _gi("U1-T2", 0.0), _gi("U1-P1", 3.5)],
    )
    # 0.4*3.0 + 0.3*2.0 + 0.3*3.5 = 2.85
    assert e["tareas"] == 2.0
    assert e["nota_final"] == 2.85
    assert e["nivel_riesgo"] == "CRITICO"


def test_sincronizacion_importa_todos_los_matriculados(monkeypatch):
    class MoodleGrande(FakeMoodle):
        async def get_courses(self):
            return [{"id": 5, "shortname": "SOF-MCS-A", "idnumber": "SOF-MCS-A", "fullname": "(SOF) MCS - A"}]

        async def get_enrolled_users(self, course_id):
            profesor = {"id": 1, "fullname": "Docente", "email": "rgomez@uta.edu.ec", "roles": [{"shortname": "editingteacher"}]}
            return [profesor] + [
                {"id": 100 + i, "fullname": f"Alumno {i}", "email": f"a{i}@uta.edu.ec", "idnumber": f"U-{i:02d}",
                 "roles": [{"shortname": "student"}]} for i in range(3, 18)
            ]

        async def get_grade_items(self, course_id):
            return [{"userid": 100 + i, "gradeitems": [_gi("U1-A1", float(i % 10)), _gi("U1-T1", 7.0), _gi("U1-P1", 7.0)]}
                    for i in range(3, 18)]

    monkeypatch.setattr(sync_service, "MoodleClient", lambda: MoodleGrande())
    res = client.post("/api/sincronizacion", headers=_auth(DOCENTE)).json()
    assert res["total_estudiantes"] == 15
    assert res["cursos"][0]["total_estudiantes"] == 15


# ---------------------------------------------------------------- Cliente Moodle
def test_cliente_moodle_usa_url_host_header_y_token(monkeypatch):
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["url"] = str(request.url)
        capturado["host"] = request.headers["host"]
        capturado["body"] = request.content.decode()
        return httpx.Response(200, json={"sitename": "Moodle UTA", "release": "4.3.2"})

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        moodle_module.httpx, "AsyncClient",
        lambda **kw: real_async_client(transport=httpx.MockTransport(handler), **kw),
    )

    mc = MoodleClient(base_url="http://moodle:8080", token="tok123", host_header="localhost")
    info = asyncio.run(mc.test_connection())

    assert info["conectado"] is True and info["sitio"] == "Moodle UTA"
    assert capturado["url"] == "http://moodle:8080/webservice/rest/server.php"
    assert capturado["host"] == "localhost"
    assert "wstoken=tok123" in capturado["body"]
    assert "wsfunction=core_webservice_get_site_info" in capturado["body"]


def test_cliente_moodle_reporta_excepcion_ws(monkeypatch):
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        moodle_module.httpx, "AsyncClient",
        lambda **kw: real_async_client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={
                "exception": "moodle_exception", "errorcode": "invalidtoken", "message": "Token no válido"})),
            **kw),
    )
    with pytest.raises(MoodleError, match="Token no válido"):
        asyncio.run(MoodleClient(token="x").call("core_course_get_courses"))
