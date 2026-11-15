"""Guía de estudio institucional en PDF que se adjunta a cada tarea de refuerzo en Moodle."""

from datetime import datetime

import pytest

from app.services import contenidos_academicos as ca
from app.services.guia_pdf import RUBRICA, construir_guia, nombre_archivo, renderizar_pdf

ESTUDIANTE = {"nombres": "Carlos Andrés Mendoza Paredes", "cedula": "1804923199",
              "email": "cmendoza3199@uta.edu.ec", "id_number": "U-04"}
REGISTRO = {"nota_final": 3.04, "nivel_riesgo": "CRITICO", "acd": 3.0, "tareas": 2.0, "pae": 3.5, "actividades": [
    {"id_number": "U2-T4", "nombre": "Tarea 4", "unidad": "U2", "nota": None, "estado": "SIN_ENTREGA"},
    {"id_number": "U2-T3", "nombre": "Tarea 3", "unidad": "U2", "nota": 2.0, "estado": "CALIFICADO"},
    {"id_number": "U2-A2", "nombre": "Evaluación", "unidad": "U2", "nota": 9.0, "estado": "CALIFICADO"},
    {"id_number": "U1-T1", "nombre": "Tarea 1", "unidad": "U1", "nota": 1.0, "estado": "CALIFICADO"}]}
CURSO = {"shortname": "SOF-POO-A", "fullname": "(SOF) PROGRAMACION ORIENTADA A OBJETOS - A"}


def _guia(**cambios):
    datos = dict(estudiante=ESTUDIANTE, curso=CURSO, unidad="Unidad 2", docente="Roberto Patricio Gómez Salazar",
                 titulo="Refuerzo Unidad 2", instrucciones="Resuelva la guía.",
                 fecha_entrega=datetime(2026, 11, 22, 23, 59), registro=REGISTRO)
    return construir_guia(**{**datos, **cambios})


def test_la_rubrica_suma_100():
    assert sum(peso for _, peso, *_ in RUBRICA) == 100
    assert all(len(descriptores) == 4 for _, _, *descriptores in RUBRICA)


def test_guia_con_datos_reales_del_estudiante_y_la_unidad_con_falencia():
    guia = _guia()
    assert guia["estudiante"]["nombres"] == "Carlos Andrés Mendoza Paredes"
    assert guia["estudiante"]["cedula"] == "1804923199"
    assert guia["materia"] == "Programación orientada a objetos — Paralelo A"
    assert guia["unidad_titulo"] == "Unidad 2: Herencia y polimorfismo"
    assert [t for t, _ in guia["temas"]] == ["Herencia", "Sobrescritura y clases abstractas", "Polimorfismo"]
    assert len(guia["ejemplo"]["pasos"]) >= 3 and guia["ejercicios"]
    # Diagnóstico: sólo las actividades débiles de la unidad, primero las que no tienen entrega
    assert [a[0] for a in guia["diagnostico"]["actividades"]] == ["U2-T4", "U2-T3"]
    assert guia["diagnostico"]["componentes"][0] == ("Exámenes", 40, 3.0)
    assert nombre_archivo(guia) == "Guia_refuerzo_POO_U2_U-04.pdf"


@pytest.mark.parametrize("sigla", sorted(ca.CONTENIDOS))
def test_catalogo_completo_y_cada_guia_se_renderiza(sigla):
    assert sorted(ca.CONTENIDOS[sigla]) == [1, 2, 3, 4]
    for unidad, contenido in ca.CONTENIDOS[sigla].items():
        assert len(contenido["temas"]) >= 3 and len(contenido["ejercicios"]) >= 4
        assert contenido["ejemplo"]["pasos"] and contenido["ejemplo"]["resultado"]
        pdf = renderizar_pdf(_guia(curso={"shortname": f"SOF-{sigla}-A", "fullname": f"(SOF) {sigla} - A"},
                                   unidad=f"Unidad {unidad}"))
        assert pdf.startswith(b"%PDF-") and pdf.rstrip().endswith(b"%%EOF")


def test_materia_fuera_del_catalogo_usa_una_guia_generica():
    guia = _guia(curso={"shortname": "SOF-XYZ-A", "fullname": "(SOF) OTRA MATERIA - A"})
    assert guia["ejemplo"] is None
    assert guia["temas"][0][0] == "Tarea 4" and guia["ejercicios"][0].startswith("Rehaga la actividad U2-T4")
    assert renderizar_pdf(guia).startswith(b"%PDF-")


def test_sin_registro_omite_el_diagnostico_y_tolera_texto_fuera_de_latin1():
    guia = _guia(registro=None, titulo="Refuerzo — «U2» → ≥ 7")
    assert guia["diagnostico"] is None
    assert renderizar_pdf(guia).startswith(b"%PDF-")
