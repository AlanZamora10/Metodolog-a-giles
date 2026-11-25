"""
Material de clase real de Moodle (RF-04 / RF-10): la sincronización lee los recursos PDF publicados por sección y
unidad, los guarda en la base y las guías de refuerzo citan sus nombres exactos.
"""

from datetime import datetime

from fastapi.testclient import TestClient

from app import database, repositories
from app.main import app
from app.routers import courses as courses_router
from app.services import sync_service
from app.services.guia_pdf import construir_guia
from moodle_fake import FakeMoodleSprint3

from test_fase_a import sincronizado  # noqa: F401 (fixture)

client = TestClient(app)


def test_la_sincronizacion_lee_solo_los_pdf_del_aula_virtual(sincronizado):  # noqa: F811
    curso = next(c for c in sync_service.SYNC_STATE["cursos"] if c["id"] == 2)
    assert curso["materiales"] == [
        {"moodle_cmid": 100, "titulo": "Sílabo de la asignatura", "archivo": "Silabo_SOF-POO-A.pdf",
         "seccion": "Informativo", "numero_seccion": 0, "parcial": None, "unidad": None},
        {"moodle_cmid": 110, "titulo": "Unidad 1 - Material de clase (PDF)", "archivo": "Unidad_1_SOF-POO-A.pdf",
         "seccion": "Primer Parcial", "numero_seccion": 1, "parcial": 1, "unidad": 1},
        {"moodle_cmid": 111, "titulo": "Unidad 2 - Guía de herencia y polimorfismo",
         "archivo": "Guia_Herencia_y_Polimorfismo.pdf", "seccion": "Primer Parcial", "numero_seccion": 1,
         "parcial": 1, "unidad": 2},
    ]   # sin enlaces ni archivos .docx
    # Persistido: sobrevive a un reinicio del middleware
    assert repositories.load_materiales()["SOF-POO-A"] == curso["materiales"]


def test_endpoint_de_materiales_y_permisos(sincronizado):  # noqa: F811
    res = client.get("/api/v1/courses/2/materiales", headers=sincronizado)
    assert res.status_code == 200
    assert [m["archivo"] for m in res.json()["materiales"]][-1] == "Guia_Herencia_y_Polimorfismo.pdf"
    assert client.get("/api/v1/courses/3/materiales", headers=sincronizado).status_code == 403


def test_un_pdf_nuevo_se_detecta_al_sincronizar_materiales(sincronizado, monkeypatch):  # noqa: F811
    monkeypatch.setattr(courses_router, "MoodleClient", lambda: FakeMoodleSprint3())
    monkeypatch.setattr(FakeMoodleSprint3, "MATERIAL_EXTRA", [
        {"id": 120, "name": "Unidad 2 - Ejercicios resueltos", "modname": "resource",
         "contents": [{"type": "file", "filename": "Ejercicios_Unidad2.pdf", "mimetype": "application/pdf"}]}])
    res = client.post("/api/v1/courses/2/materiales/sincronizar", headers=sincronizado)
    assert res.status_code == 200
    assert "Ejercicios_Unidad2.pdf" in [m["archivo"] for m in res.json()["materiales"]]
    assert "Ejercicios_Unidad2.pdf" in [m["archivo"] for m in repositories.load_materiales()["SOF-POO-A"]]
    log = repositories.filas("logs_sistema")[-1]
    assert log["tipo_proceso"] == "SINCRONIZACION_MATERIALES" and "Ejercicios_Unidad2.pdf" in log["detalle"]["archivos"]


def _guia(curso):
    return construir_guia(
        estudiante={"nombres": "Carlos Andrés Mendoza Paredes", "cedula": "1804923199", "id_number": "U-04"},
        curso=curso, unidad="Unidad 2", docente="Roberto Patricio Gómez Salazar", titulo="Refuerzo",
        instrucciones="", fecha_entrega=datetime(2026, 12, 2, 23, 59), registro=None)


def test_la_guia_cita_los_pdf_reales_de_la_unidad(sincronizado):  # noqa: F811
    curso = next(c for c in sync_service.SYNC_STATE["cursos"] if c["id"] == 2)
    guia = _guia(curso)
    assert guia["materiales"] == [{"archivo": "Guia_Herencia_y_Polimorfismo.pdf",
                                   "titulo": "Unidad 2 - Guía de herencia y polimorfismo"}]
    assert ("Revisa el material publicado en el aula virtual (Primer Parcial, Unidad 2): "
            "«Guia_Herencia_y_Polimorfismo.pdf».") in guia["instrucciones_pasos"][1]
    assert guia["recursos"][-1] == ("Aula virtual de la materia (Moodle UTA)",
                                    "material publicado en Primer Parcial, Unidad 2: «Guia_Herencia_y_Polimorfismo.pdf».")
    assert not any("Material de clase (PDF)» en la sección" in d for _, d in guia["recursos"])


def test_sin_pdf_subido_se_mantiene_la_referencia_base_de_la_unidad():
    guia = _guia({"shortname": "SOF-POO-A", "fullname": "(SOF) PROGRAMACION ORIENTADA A OBJETOS - A",
                  "materiales": []})
    assert guia["materiales"] == []
    assert "Revisa el material publicado" not in guia["instrucciones_pasos"][1]
    assert guia["recursos"][-1] == ("Aula virtual de la materia (Moodle UTA)",
                                    "recurso «Unidad 2 - Material de clase (PDF)» en la sección Primer Parcial.")


def test_si_moodle_no_permite_leer_el_contenido_la_sincronizacion_sigue():
    class SinContenido(FakeMoodleSprint3):
        async def get_course_contents(self, course_id):
            raise RuntimeError("Access control exception")

    import asyncio
    database.use_engine(database.new_sqlite_engine(), "sqlite_prueba")
    estado = asyncio.run(sync_service.sincronizar(SinContenido()))
    assert all(c["materiales"] == [] for c in estado["cursos"])
    assert estado["cursos"][0]["estudiantes"]
