"""
Sprint 3 — Regla R2 (tendencia) activa y alertas dinámicas en `alertas_tempranas`.

  - R1: nota < 5.00.  R2: pendiente entre unidades < -0.25 y nota < 7.00 (R1 tiene prioridad).
  - Decisión (a): R2 genera la alerta y la tendencia BAJA, pero NO cambia el nivel de riesgo.
  - Ciclo de vida: ABIERTA -> ATENDIDA (agente IA / respaldo) -> PUBLICADO | CERRADA; RESUELTA automática.
"""

import pytest
from fastapi.testclient import TestClient

from app import database, repositories
from app.main import app
from app.services import sync_service
from app.services.grade_calculator import GradeCalculator
from moodle_fake import DOCENTE, FakeMoodleSprint3, gi

client = TestClient(app)
R1, R2 = GradeCalculator.REGLA_R1, GradeCalculator.REGLA_R2


# ------------------------------------------------------------------ Reglas puras
@pytest.mark.parametrize("nota,pendiente,esperada", [
    (6.50, -3.00, R2),     # caída fuerte con nota < 7
    (6.50, -0.26, R2),     # justo por debajo del umbral
    (6.50, -0.25, None),   # en el umbral: no dispara
    (7.20, -2.00, None),   # cae pero la nota es aceptable
    (4.80, 0.50, R1),      # R1 aunque mejore
    (4.80, -1.00, R1),     # R1 tiene prioridad sobre R2
    (6.00, None, None),    # sin pendiente no hay R2
])
def test_evaluate_alert_rule(nota, pendiente, esperada):
    assert GradeCalculator.evaluate_alert_rule(nota, pendiente) == esperada


def _alumno(items):
    return sync_service.construir_estudiante(
        {"id": 1, "fullname": "Alumno", "idnumber": "U-50", "roles": [{"shortname": "student"}]}, items)


def test_r2_se_activa_con_caida_de_rendimiento():
    e = _alumno([gi("U1-A1", 8.0), gi("U1-T1", 8.0), gi("U1-P1", 8.0),
                 gi("U2-A2", 5.0), gi("U2-T3", 5.0), gi("U2-P3", 5.0)])
    assert e["promedios_unidad"] == {"U1": 8.0, "U2": 5.0}
    assert e["pendiente"] == -3.0
    assert e["tendencia"] == "BAJA"
    assert e["nota_final"] == 6.50
    assert e["regla_alerta"] == R2
    assert e["nivel_riesgo"] == "EN_RIESGO"  # decisión (a): el nivel no cambia


def test_r2_no_se_activa_con_caida_leve():
    e = _alumno([gi("U1-A1", 6.0), gi("U1-T1", 6.0), gi("U1-P1", 6.0),
                 gi("U2-A2", 5.75), gi("U2-T3", 5.75), gi("U2-P3", 5.75)])
    assert e["pendiente"] == -0.25
    assert e["tendencia"] == "ESTABLE"
    assert e["regla_alerta"] is None


def test_una_sola_unidad_no_tiene_pendiente():
    e = _alumno([gi("U1-A1", 6.0), gi("U1-T1", 6.0), gi("U1-P1", 6.0)])
    assert e["pendiente"] == 0.0 and e["regla_alerta"] is None


def test_pendiente_ignora_actividades_pendientes():
    e = _alumno([gi("U1-A1", 8.0), gi("U1-T1", 8.0), gi("U1-P1", 8.0), gi("U2-P3", None, "PENDIENTE")])
    assert e["promedios_unidad"] == {"U1": 8.0}
    assert e["regla_alerta"] is None


def test_sin_entrega_cuenta_en_la_pendiente():
    e = _alumno([gi("U1-A1", 6.5), gi("U1-T1", 6.5), gi("U1-P1", 6.5),
                 gi("U2-A2", 6.5), gi("U2-T4", None, "SIN ENTREGA"), gi("U2-P3", 6.5)])
    assert e["promedios_unidad"]["U2"] == round((6.5 + 0 + 6.5) / 3, 2)
    assert e["pendiente"] < -0.25


# ------------------------------------------------------------------ Alertas dinámicas en la base
@pytest.fixture
def fake(monkeypatch):
    database.use_engine(database.new_sqlite_engine(), "sqlite_prueba")
    sync_service.SYNC_STATE.update({"ultima_sincronizacion": None, "moodle": None, "cursos": []})
    moodle = FakeMoodleSprint3()
    monkeypatch.setattr(sync_service, "MoodleClient", lambda: moodle)
    yield moodle


@pytest.fixture
def headers(fake):
    res = client.post("/api/v1/auth/login", json=DOCENTE)
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _alertas(headers, **params):
    res = client.get("/api/v1/alertas", headers=headers, params={"course_id": 2, **params})
    assert res.status_code == 200, res.text
    return {a["id_number"]: a for a in res.json()}


def test_sincronizar_genera_alertas_r1_y_r2(headers):
    client.post("/api/sincronizacion", headers=headers)
    alertas = _alertas(headers)
    assert set(alertas) == {"U-04", "U-11"}

    r1 = alertas["U-04"]
    assert r1["regla"] == R1 and r1["nivel"] == "CRITICO" and r1["estado"] == "ABIERTA"
    assert r1["nota_promedio"] == 2.65
    assert "SIN_ENTREGA" in r1["evidencia"]

    r2 = alertas["U-11"]
    assert r2["regla"] == R2 and r2["nivel"] == "EN_RIESGO"
    assert r2["pendiente"] == -3.0
    assert r2["unidad_critica"] == "Unidad 2"

    # El panel sigue mostrando el nivel por nota (decisión a)
    curso = client.get("/api/cursos/2/estudiantes", headers=headers).json()
    assert (curso["criticos"], curso["en_riesgo"], curso["aceptables"]) == (1, 1, 2)
    assert (curso["alertas_r1"], curso["alertas_r2"]) == (1, 1)

    # Persistidas en alertas_tempranas (2 por curso)
    assert repositories.contar("alertas_tempranas") == 4


def test_resincronizar_no_duplica_y_resuelve_al_recuperarse(fake, headers):
    client.post("/api/sincronizacion", headers=headers)
    client.post("/api/sincronizacion", headers=headers)
    assert repositories.contar("alertas_tempranas") == 4

    fake.recuperado = True  # U-11 recupera en la Unidad 2
    client.post("/api/sincronizacion", headers=headers)
    assert set(_alertas(headers, estado="ABIERTA")) == {"U-04"}
    assert _alertas(headers, estado="RESUELTA")["U-11"]["regla"] == R2

    fake.recuperado = False  # vuelve a caer: la alerta resuelta se reabre (no se duplica)
    client.post("/api/sincronizacion", headers=headers)
    assert set(_alertas(headers, estado="ABIERTA")) == {"U-04", "U-11"}
    assert repositories.contar("alertas_tempranas") == 4


def test_ciclo_de_vida_atender_publicar_cerrar(headers):
    client.post("/api/sincronizacion", headers=headers)
    alertas = _alertas(headers)
    r1, r2 = alertas["U-04"]["id"], alertas["U-11"]["id"]

    # Atender: el agente no está disponible en pruebas -> respaldo determinista, borrador en `refuerzos`
    res = client.post(f"/api/v1/alertas/{r1}/atender", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["alerta"]["estado"] == "ATENDIDA"
    assert data["refuerzo"]["origen"] == "MOTOR_HEURISTICO_HU11B"
    assert data["refuerzo"]["estado"] == "BORRADOR"
    assert "SOF-POO-A" in data["refuerzo"]["titulo"]
    assert repositories.get_refuerzo(alerta_id=r1)["id"] == data["refuerzo"]["id"]
    log = repositories.filas("logs_sistema")[-1]
    assert log["tipo_proceso"] == "ATENCION_ALERTA" and log["detalle"]["origen"] == "motor_heuristico_hu11b"

    # Re-sincronizar no pisa una alerta ATENDIDA
    client.post("/api/sincronizacion", headers=headers)
    assert _alertas(headers)["U-04"]["estado"] == "ATENDIDA"

    # Publicar exige confirmación explícita (RN-17)
    refuerzo_id = data["refuerzo"]["id"]
    assert client.post(f"/api/v1/refuerzos/{refuerzo_id}/publicar", headers=headers,
                       json={"confirmado": False}).status_code == 400
    pub = client.post(f"/api/v1/refuerzos/{refuerzo_id}/publicar", headers=headers,
                      json={"confirmado": True, "titulo": "Refuerzo editado"})
    assert pub.status_code == 200
    assert pub.json()["refuerzo"]["estado"] == "PUBLICADO"
    assert pub.json()["refuerzo"]["titulo"] == "Refuerzo editado"
    assert _alertas(headers)["U-04"]["estado"] == "PUBLICADO"
    assert client.post(f"/api/v1/alertas/{r1}/atender", headers=headers).status_code == 409

    # Cerrar es terminal (RN-14)
    assert client.patch(f"/api/v1/alertas/{r2}/cerrar", headers=headers).json()["alerta"]["estado"] == "CERRADA"
    assert client.patch(f"/api/v1/alertas/{r2}/cerrar", headers=headers).status_code == 409
    assert client.post(f"/api/v1/alertas/{r2}/atender", headers=headers).status_code == 409


def test_ponderada_guarda_tendencia_y_pendiente(headers):
    client.post("/api/sincronizacion", headers=headers)
    est = {e["id"]: e["id_number"] for e in repositories.filas("estudiantes")}
    filas = [p for p in repositories.filas("calificaciones_ponderadas") if est[p["estudiante_id"]] == "U-11"]
    assert filas and all(p["tendencia"] == "BAJA" and p["pendiente_regresion"] == -3.0 for p in filas)
    assert all(p["nivel_riesgo"] == "EN_RIESGO" for p in filas)
