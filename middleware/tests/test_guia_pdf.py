"""Guía de estudio en PDF (material de apoyo breve) que se adjunta a cada tarea de refuerzo en Moodle."""

import re
from datetime import datetime

import pytest

from app.services import contenidos_academicos as ca
from app.services import guia_pdf
from app.services.guia_pdf import construir_guia, indicaciones_estudiante, nombre_archivo, renderizar_pdf

ESTUDIANTE = {"nombres": "Carlos Andrés Mendoza Paredes", "cedula": "1804923199",
              "email": "cmendoza3199@uta.edu.ec", "id_number": "U-04"}
REGISTRO = {"nota_final": 6.45, "nivel_riesgo": "EN_RIESGO", "acd": 6.9, "tareas": 6.31, "pae": 6.6,
            "promedios_unidad": {"U1": 7.1, "U2": 5.94}, "actividades": [
                {"id_number": "U2-T4", "nombre": "Tarea 4", "unidad": 2, "nota": 6.0, "estado": "CALIFICADO"},
                {"id_number": "U2-T3", "nombre": "Tarea 3", "unidad": 2, "nota": 6.0, "estado": "CALIFICADO"},
                {"id_number": "U2-A2", "nombre": "Evaluación", "unidad": 2, "nota": 5.5, "estado": "CALIFICADO"},
                {"id_number": "U2-P3", "nombre": "Práctica 3", "unidad": 2, "nota": 6.5, "estado": "CALIFICADO"},
                {"id_number": "U2-T5", "nombre": "Tarea 5", "unidad": 2, "nota": 9.0, "estado": "CALIFICADO"},
                {"id_number": "U1-T1", "nombre": "Tarea 1", "unidad": 1, "nota": 1.0, "estado": "CALIFICADO"}]}
CURSO = {"shortname": "SOF-POO-A", "fullname": "(SOF) PROGRAMACION ORIENTADA A OBJETOS - A"}


def _guia(**cambios):
    datos = dict(estudiante=ESTUDIANTE, curso=CURSO, unidad="Unidad 2", docente="Roberto Patricio Gómez Salazar",
                 titulo="Refuerzo Unidad 2", instrucciones="Resuelva la guía.",
                 fecha_entrega=datetime(2026, 11, 22, 23, 59), registro=REGISTRO)
    return construir_guia(**{**datos, **cambios})


def _paginas(pdf: bytes) -> int:
    return len(re.findall(rb"/Type /Page\b(?!s)", pdf))


def test_es_una_guia_de_estudio_sin_rubrica_ni_criterios_de_calificacion():
    guia = _guia()
    assert "rubrica" not in guia and not hasattr(guia_pdf, "RUBRICA")
    assert set(guia) >= {"estudiante", "materia", "unidad_titulo", "docente", "diagnostico", "indicaciones",
                         "temas", "ejemplo", "ejercicios"}


def test_datos_esenciales_del_estudiante_y_la_unidad():
    guia = _guia()
    assert guia["estudiante"] == ESTUDIANTE
    assert guia["materia"] == "Programación orientada a objetos — Paralelo A"
    assert guia["unidad_titulo"] == "Unidad 2: Herencia y polimorfismo"
    assert guia["docente"] == "Roberto Patricio Gómez Salazar"
    assert nombre_archivo(guia) == "Guia_refuerzo_POO_U2_U-04.pdf"


def test_diagnostico_en_cuatro_tarjetas_metricas():
    assert _guia()["diagnostico"] == [
        ("Nota de la Unidad 2", "5.94 / 10"),
        ("Nota ponderada y estado", "6.45 / 10 (Nivel: En riesgo)"),
        ("Componente a reforzar", "Tareas (6.31 / 10)"),
        ("Actividades a repasar", "U2-A2 (5.50), U2-T4 (6.00), U2-T3 (6.00)"),   # sólo de la unidad, máx. 3
    ]


def test_indicaciones_con_tono_cercano_de_profesor_y_los_subtemas_de_la_unidad():
    texto = indicaciones_estudiante("Carlos Andrés Mendoza Paredes", 2, "Herencia y polimorfismo",
                                    ["Herencia", "Sobrescritura y clases abstractas", "Polimorfismo"],
                                    datetime(2026, 11, 22, 23, 59))
    assert texto == ("Hola Carlos, revisando tus calificaciones de la Unidad 2 (Herencia y polimorfismo), te comparto "
                     "esta guía de apoyo para fortalecer herencia, sobrescritura y clases abstractas y polimorfismo antes "
                     "de tu actividad de recuperación. Revisa primero la fundamentación y el material recomendado, analiza "
                     "el ejemplo paso a paso, resuelve los ejercicios de la sección VIII y sube tu archivo (PDF o código) en "
                     "la tarea de Moodle UTA hasta el 22/11/2026 a las 23:59.")
    for robotico in ("Estimado/a", "se ha identificado", "EduMonitor", "IA"):
        assert robotico not in texto
    # Siglas al inicio del subtema se conservan
    assert "fortalecer SQL avanzado" in indicaciones_estudiante("Ana", 2, "SQL", ["SQL avanzado"])
    assert "hasta la fecha indicada en la tarea" in indicaciones_estudiante("Ana", 2, "SQL", ["SQL avanzado"])


@pytest.mark.parametrize("instrucciones, empieza, contiene", [
    # Textos que no escribió el docente (borrador en tercera persona o mensaje de una versión anterior): se reemplazan
    ("El estudiante Carlos Mendoza presenta dificultades en Unidad 2.", "Hola Carlos, revisando", None),
    ("Estimado/a Carlos, se ha identificado que necesitas reforzar los temas de herencia.", "Hola Carlos, revisando", None),
    ("", "Hola Carlos, revisando", None),
    # Indicación propia del docente: se conserva como observación tras el mensaje con los subtemas
    ("Resuelva la guía.", "Hola Carlos, revisando", "Observación de tu docente: Resuelva la guía."),
    # El docente ya le escribe al estudiante: se respeta su texto
    ("Estimado Carlos, revisa la herencia múltiple.", "Estimado Carlos, revisa", None),
])
def test_indicaciones_respetan_lo_que_escribio_el_docente(instrucciones, empieza, contiene):
    indicaciones = _guia(instrucciones=instrucciones)["indicaciones"]
    assert indicaciones.startswith(empieza)
    assert "presenta dificultades" not in indicaciones and "se ha identificado" not in indicaciones
    if contiene:
        assert contiene in indicaciones


def test_donde_consultar_y_reforzar_con_fuentes_reales_y_el_aula_virtual():
    recursos = _guia()["recursos"]
    assert len(recursos) == 3
    assert recursos[0] == ("Deitel y Deitel, «Cómo programar en Java», 10.ª ed., Pearson",
                           "caps. 9 y 10: herencia, clases abstractas y polimorfismo.")
    assert recursos[-1] == ("Aula virtual de la materia (Moodle UTA)",
                            "recurso «Unidad 2 - Material de clase (PDF)» en la sección Primer Parcial.")
    assert ca.recursos_unidad("SOF-BDA-B", 4)[-1][1].endswith("en la sección Segundo Parcial.")


@pytest.mark.parametrize("sigla", sorted(ca.CONTENIDOS))
def test_cada_unidad_tiene_dos_fuentes_ademas_del_aula_virtual(sigla):
    assert sorted(ca.RECURSOS[sigla]) == [1, 2, 3, 4]
    for unidad, fuentes in ca.RECURSOS[sigla].items():
        assert len(fuentes) == 2 and all(f and d for f, d in fuentes), (sigla, unidad)


def test_encabezado_institucional_uta_sin_rastros_de_ia():
    import inspect
    assert guia_pdf.UNIVERSIDAD == "UNIVERSIDAD TÉCNICA DE AMBATO"
    assert guia_pdf.SUBTITULO == "GUÍA DE REFUERZO ACADÉMICO Y APLICACIÓN DE APRENDIZAJES"
    assert guia_pdf.LOGO.name == "uta-logo-azul.png" and guia_pdf.LOGO.exists()
    fuente = inspect.getsource(guia_pdf)
    assert "EduMonitor" not in fuente
    assert 'f"Página {self.page_no()}/{{nb}} · {PIE}"' in fuente and guia_pdf.PIE == "UTA - FISEI"


def test_tabla_de_datos_generales_institucional():
    assert guia_pdf.datos_generales(_guia()) == [
        ("FACULTAD", "Ingeniería en Sistemas, Electrónica e Industrial (FISEI)"),
        ("CARRERA", "Software"),
        ("ASIGNATURA", "Programación orientada a objetos - Paralelo A"),
        ("NIVEL / CICLO ACADÉMICO", "Cuarto Semestre · Julio – Diciembre 2026"),
        ("DOCENTE", "Roberto Patricio Gómez Salazar"),
        ("ESTUDIANTE", "Carlos Andrés Mendoza Paredes (C.I. 1804923199 · cmendoza3199@uta.edu.ec)"),
        ("FECHA LÍMITE DE ENTREGA", "domingo 22 de noviembre de 2026, 23:59"),
    ]
    assert guia_pdf.fecha_larga(None) == "La indicada en la tarea de Moodle UTA"


def test_secciones_numeradas_en_romano_de_la_plantilla_uta():
    import inspect
    fuente = inspect.getsource(guia_pdf.renderizar_pdf)
    secciones = re.findall(r'_titulo_seccion\(pdf, "([IVX]+)", "([^"]+)"\)', fuente)
    assert secciones == [
        ("I", "Tema"), ("II", "Objetivo"), ("III", "Modalidad y duración"),
        ("IV", "Diagnóstico académico del estudiante"), ("V", "Instrucciones y orientación del docente"),
        ("VI", "Recursos y material de apoyo"), ("VII", "Fundamentación y ejemplo resuelto"),
        ("VIII", "Actividades por desarrollar (ejercicios de práctica)"), ("IX", "Resultados esperados y habilidades")]
    for excluido in ("firma", "Firma", "BIBLIOGRAF", "Coordinador"):
        assert excluido not in fuente + inspect.getsource(guia_pdf._GuiaPDF)   # sin firmas ni bibliografía


def test_tema_objetivo_modalidad_recursos_y_resultados():
    guia = _guia()
    assert guia["unidad_titulo"] == "Unidad 2: Herencia y polimorfismo"
    assert guia["subtemas"] == ["Herencia", "Sobrescritura y clases abstractas", "Polimorfismo"]
    assert guia["objetivo"] == ("Diseñar jerarquías de clases con herencia, clases abstractas y polimorfismo, "
                                "reutilizando código sin romper la relación «es un», superando las falencias "
                                "detectadas en la evaluación de la Unidad 2.")
    assert (guia["modalidad"], guia["duracion"]) == ("Virtual / Trabajo autónomo en Moodle UTA", "2 horas no presenciales")
    assert guia["entorno"].startswith("JDK 17")
    assert len(guia["resultados"]) == 3
    assert guia["resultados"][0] == ("**Dominio conceptual:** explica y aplica herencia, sobrescritura y clases "
                                     "abstractas y polimorfismo (Unidad 2).")
    assert "Pensamiento crítico y responsabilidad académica" in guia["resultados"][2]


@pytest.mark.parametrize("sigla", sorted(ca.CONTENIDOS))
def test_cada_materia_tiene_objetivo_por_unidad_entorno_y_habilidad(sigla):
    assert sorted(ca.OBJETIVOS[sigla]) == [1, 2, 3, 4]
    assert all(o and not o.endswith(".") for o in ca.OBJETIVOS[sigla].values())
    assert ca.ENTORNOS[sigla] and ca.HABILIDADES[sigla][0].islower()


@pytest.mark.parametrize("sigla", sorted(ca.CONTENIDOS))
def test_textos_con_negritas_no_usan_marcas_markdown_accidentales(sigla):
    # Conceptos, recursos y resultados se dibujan con markdown=True: «--» o «__» cambiarían el formato
    textos = [t for u in ca.CONTENIDOS[sigla].values() for par in u["temas"] for t in par]
    textos += [t for fuentes in ca.RECURSOS[sigla].values() for par in fuentes for t in par]
    textos += [ca.ENTORNOS[sigla], ca.HABILIDADES[sigla]]
    for texto in textos:
        assert "--" not in texto and "__" not in texto and "**" not in texto, texto


def test_material_al_grano_un_ejemplo_y_hasta_tres_ejercicios():
    guia = _guia()
    assert [t for t, _ in guia["temas"]] == ["Herencia", "Sobrescritura y clases abstractas", "Polimorfismo"]
    assert all(len(explicacion) <= 260 for _, explicacion in guia["temas"])        # explicaciones breves
    assert guia["ejemplo"]["enunciado"] and 3 <= len(guia["ejemplo"]["pasos"]) <= 5
    assert 2 <= len(guia["ejercicios"]) <= 3


@pytest.mark.parametrize("sigla", sorted(ca.CONTENIDOS))
def test_tipografia_limpia_en_ejemplos_y_ejercicios(sigla):
    for unidad in ca.CONTENIDOS[sigla].values():
        textos = [unidad["ejemplo"]["enunciado"], unidad["ejemplo"]["resultado"], *unidad["ejemplo"]["pasos"],
                  *unidad["ejercicios"]]
        for texto in textos:
            assert "->" not in texto, texto                                     # flechas limpias (=>)
            assert not re.search(r"«[^»]*[\[\](){}+*/=<>\d][^»]*»", texto), texto   # fórmulas sin comillas angulares


def test_catalogo_incluye_las_materias_de_ambos_docentes():
    assert set(ca.CONTENIDOS) == {"POO", "ED", "MA", "MCS", "IS1", "BDA", "DW"}
    assert ca.contenido_unidad("SOF-BDA-B", 1)["titulo"] == "Modelo relacional y normalización"


@pytest.mark.parametrize("sigla", sorted(ca.CONTENIDOS))
def test_cada_guia_del_catalogo_ocupa_como_maximo_dos_paginas(sigla):
    assert sorted(ca.CONTENIDOS[sigla]) == [1, 2, 3, 4]
    for unidad in ca.CONTENIDOS[sigla]:
        pdf = renderizar_pdf(_guia(curso={"shortname": f"SOF-{sigla}-A", "fullname": f"(SOF) {sigla} - A"},
                                   unidad=f"Unidad {unidad}",
                                   instrucciones="Revise el material de la unidad y resuelva la guía. " * 3))
        assert pdf.startswith(b"%PDF-") and pdf.rstrip().endswith(b"%%EOF")
        assert 1 <= _paginas(pdf) <= 2, (sigla, unidad)


def test_la_guia_tipica_ocupa_una_o_dos_paginas():
    assert 1 <= _paginas(renderizar_pdf(_guia())) <= 2


def test_materia_fuera_del_catalogo_usa_una_guia_breve():
    guia = _guia(curso={"shortname": "SOF-XYZ-A", "fullname": "(SOF) OTRA MATERIA - A"})
    assert guia["ejemplo"] is None
    assert guia["temas"][0][0] == "Evaluación" and guia["ejercicios"][0].startswith("Rehaga la actividad U2-A2")
    assert renderizar_pdf(guia).startswith(b"%PDF-")


def test_sin_registro_omite_el_diagnostico_y_tolera_texto_fuera_de_latin1():
    guia = _guia(registro=None, titulo="Refuerzo — «U2» → ≥ 7")
    assert guia["diagnostico"] == []
    assert renderizar_pdf(guia).startswith(b"%PDF-")


def test_el_titulo_muestra_la_materia_y_no_el_codigo_del_curso():
    guia = _guia(titulo="Refuerzo: Refuerzo Didáctico Guiado (Unidad 2) — SOF-POO-A")
    assert guia["titulo"] == "Refuerzo: Refuerzo Didáctico Guiado (Unidad 2) — Programación orientada a objetos — Paralelo A"
