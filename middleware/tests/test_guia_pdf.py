"""Guía de refuerzo en PDF (formulario sobrio UTA - FISEI, blanco y negro) que se adjunta a cada tarea en Moodle."""

import re
import zlib
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


def test_es_una_guia_de_refuerzo_sin_rubrica_ni_tarjetas():
    guia = _guia()
    assert "rubrica" not in guia and not hasattr(guia_pdf, "RUBRICA")
    assert "diagnostico" not in guia and not hasattr(guia_pdf, "_tarjetas")
    assert set(guia) >= {"estudiante", "materia", "unidad_titulo", "docente", "objetivo", "instrucciones_pasos",
                         "temas", "ejemplo", "ejercicios", "recursos", "entorno"}


def test_datos_esenciales_del_estudiante_y_la_unidad():
    guia = _guia()
    assert guia["estudiante"] == ESTUDIANTE
    assert guia["materia"] == "Programación orientada a objetos — Paralelo A"
    assert guia["unidad_titulo"] == "Unidad 2: Herencia y polimorfismo"
    assert guia["docente"] == "Roberto Patricio Gómez Salazar"
    assert nombre_archivo(guia) == "Guia_refuerzo_POO_U2_U-04.pdf"


def test_las_notas_reales_que_motivan_el_refuerzo():
    assert _guia()["motivo"] == ("promedio de la unidad 5.94/10; actividades más bajas: Evaluación (5.50), Tarea 4 "
                                 "(6.00) y Tarea 3 (6.00); nota ponderada actual 6.45/10 (en riesgo)")   # máx. 3
    assert _guia(registro=None)["motivo"] is None


def test_instrucciones_en_pasos_cortos_motivo_repaso_y_entrega():
    intro, pasos = guia_pdf.instrucciones_estudiante(
        "Carlos Andrés Mendoza Paredes", 2, "Herencia y polimorfismo",
        ["Herencia", "Sobrescritura y clases abstractas", "Polimorfismo"], datetime(2026, 11, 22, 23, 59),
        motivo="promedio de la unidad 5.94/10")
    assert intro == "Carlos, este refuerzo corresponde a la Unidad 2 (Herencia y polimorfismo)."
    assert pasos == [
        "**Motivo académico:** promedio de la unidad 5.94/10.",
        "**Qué repasar:** herencia, sobrescritura y clases abstractas y polimorfismo, con la fundamentación y el "
        "ejemplo resuelto de la sección VI.",
        "**Entrega:** resuelve las actividades de la sección VII y sube un único archivo PDF (o tu código comprimido "
        "en .zip) en la tarea de Moodle UTA hasta el 22/11/2026 a las 23:59.",
    ]
    for robotico in ("Estimado/a", "se ha identificado", "EduMonitor", "IA", "Hola"):
        assert all(robotico not in t for t in [intro, *pasos])
    # Siglas al inicio del subtema se conservan; sin fecha se remite a la tarea
    _, pasos_sql = guia_pdf.instrucciones_estudiante("Ana", 2, "SQL", ["SQL avanzado"])
    assert "SQL avanzado" in pasos_sql[1] and "hasta la fecha indicada en la tarea" in pasos_sql[2]
    assert pasos_sql[0].startswith("**Motivo académico:** reforzar los contenidos de la Unidad 2")


def test_texto_para_moodle_numerado_y_sin_marcas():
    texto = indicaciones_estudiante("Carlos Andrés", 2, "Herencia y polimorfismo", ["Herencia"],
                                    datetime(2026, 11, 22, 23, 59), motivo="promedio de la unidad 5.94/10")
    lineas = texto.split("\n")
    assert lineas[0] == "Carlos, este refuerzo corresponde a la Unidad 2 (Herencia y polimorfismo)."
    assert [ln[:3] for ln in lineas[1:]] == ["1. ", "2. ", "3. "] and "**" not in texto


@pytest.mark.parametrize("instrucciones, observacion", [
    # Textos que no escribió el docente (borrador en tercera persona o de versiones anteriores): se descartan
    ("El estudiante Carlos Mendoza presenta dificultades en Unidad 2.", None),
    ("Estimado/a Carlos, se ha identificado que necesitas reforzar los temas de herencia.", None),
    ("Hola Carlos, revisando tus calificaciones de la Unidad 2, te comparto esta guía.", None),
    ("Carlos, este refuerzo corresponde a la Unidad 2 (Herencia y polimorfismo).\n1. Motivo...", None),
    ("", None),
    # Lo que escribió el propio docente se conserva como un paso más («Observación del docente»)
    ("Resuelva la guía.", "Resuelva la guía."),
    ("Estimado Carlos, revisa la herencia múltiple.", "Estimado Carlos, revisa la herencia múltiple."),
])
def test_instrucciones_respetan_lo_que_escribio_el_docente(instrucciones, observacion):
    guia = _guia(instrucciones=instrucciones)
    assert guia["instrucciones_intro"].startswith("Carlos, este refuerzo corresponde a la Unidad 2")
    assert guia["observacion"] == observacion
    pasos = guia["instrucciones_pasos"]
    assert pasos[0].startswith("**Motivo académico:** promedio de la unidad 5.94/10")
    if observacion:
        assert len(pasos) == 4 and pasos[-1] == f"**Observación del docente:** {observacion}"
    else:
        assert len(pasos) == 3
    assert not any("presenta dificultades" in p or "se ha identificado" in p for p in pasos)


def test_referencia_recomendada_al_pie_de_la_fundamentacion():
    assert _guia()["referencia"] == ("Deitel y Deitel, «Cómo programar en Java», 10.ª ed., Pearson",
                                     "caps. 9 y 10: herencia, clases abstractas y polimorfismo.")
    # Se prefiere un libro aunque no sea la primera fuente de la unidad
    assert ca.referencia_unidad("SOF-MA-A", 2)[0] == "Schwaber y Sutherland, «La Guía Scrum» (2020)"
    assert ca.referencia_unidad("SOF-XYZ-A", 1) is None
    import inspect
    assert "**Libro / referencia recomendada:**" in inspect.getsource(guia_pdf.renderizar_pdf)


# Unidades de cada materia: 4 (Primer y Segundo Parcial); Cálculo (Telecomunicaciones) tiene 2 en su documento
_UNIDADES = {sigla: [1, 2] if sigla == "CAL" else [1, 2, 3, 4] for sigla in ca.CONTENIDOS}


@pytest.mark.parametrize("sigla", sorted(ca.CONTENIDOS))
def test_cada_unidad_tiene_referencia_recomendada(sigla):
    assert all(ca.referencia_unidad(f"SOF-{sigla}-A", u) for u in _UNIDADES[sigla])


def test_material_y_recursos_con_fuentes_reales_y_el_aula_virtual():
    guia = _guia()
    assert guia["entorno"].startswith("JDK 17")
    recursos = guia["recursos"]
    assert len(recursos) == 3
    assert recursos[0] == ("Deitel y Deitel, «Cómo programar en Java», 10.ª ed., Pearson",
                           "caps. 9 y 10: herencia, clases abstractas y polimorfismo.")
    assert recursos[-1] == ("Aula virtual de la materia (Moodle UTA)",
                            "recurso «Unidad 2 - Material de clase (PDF)» en la sección Primer Parcial.")
    assert ca.recursos_unidad("SOF-BDA-B", 4)[-1][1].endswith("en la sección Segundo Parcial.")


@pytest.mark.parametrize("sigla", sorted(ca.CONTENIDOS))
def test_cada_unidad_tiene_dos_fuentes_ademas_del_aula_virtual(sigla):
    assert sorted(ca.RECURSOS[sigla]) == _UNIDADES[sigla]
    for unidad, fuentes in ca.RECURSOS[sigla].items():
        assert len(fuentes) == 2 and all(f and d for f, d in fuentes), (sigla, unidad)


def test_encabezado_institucional_uta_sin_rastros_de_ia():
    import inspect
    assert guia_pdf.UNIVERSIDAD == "UNIVERSIDAD TÉCNICA DE AMBATO"
    assert guia_pdf.SUBTITULO == "GUÍA DE REFUERZO ACADÉMICO Y APLICACIÓN DE APRENDIZAJES"
    assert guia_pdf.LOGO.exists()
    assert guia_pdf._escudo().size == (197, 210)          # sólo el escudo, sin la marca nominativa
    fuente = inspect.getsource(guia_pdf)
    assert "EduMonitor" not in fuente
    assert 'f"Página {self.page_no()}/{{nb}} · {PIE}"' in fuente and guia_pdf.PIE == "UTA - FISEI"


def _flujos(pdf: bytes) -> bytes:
    """Contenido descomprimido de todos los flujos del PDF (operadores de dibujo)."""
    salida = b""
    for crudo in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S):
        try:
            salida += zlib.decompress(crudo)
        except zlib.error:
            salida += crudo
    return salida


def test_paleta_cien_por_ciento_blanco_y_negro():
    import inspect
    fuente = inspect.getsource(guia_pdf)
    assert guia_pdf.NEGRO == (0, 0, 0)
    assert "set_fill_color" not in fuente and "fill=True" not in fuente and "round_corners" not in fuente
    assert set(re.findall(r"set_(?:text|draw)_color\(([^)]*)\)", fuente)) == {"*NEGRO"}
    # En el PDF generado no hay ningún operador de color distinto de negro (fpdf2 omite el negro por defecto)
    flujos = _flujos(renderizar_pdf(_guia()))
    colores = set(re.findall(rb"((?:[\d.]+ ){3})(?:rg|RG)\b", flujos)) | set(re.findall(rb"([\d.]+ )(?:g|G)\b", flujos))
    assert b"BT" in flujos and b" re" in flujos                      # se leyeron el texto y los marcos
    assert all(float(v) == 0 for c in colores for v in c.split()), colores


def test_tabla_de_datos_generales_institucional():
    assert guia_pdf.datos_generales(_guia()) == [
        [("FACULTAD", "INGENIERÍA EN SISTEMAS, ELECTRÓNICA E INDUSTRIAL", 2), ("CARRERA", "Software", 1)],
        [("NIVEL", "Cuarto", 1), ("CICLO ACADÉMICO", "Julio - Diciembre 2026", 1),
         ("ASIGNATURA", "Programación orientada a objetos - Paralelo A", 1)],
        [("DOCENTE", "Roberto Patricio Gómez Salazar", 3)],
        [("ESTUDIANTE", "Carlos Andrés Mendoza Paredes — C.I. 1804923199", 3)],   # sin correo
        [("FECHA LÍMITE DE ENTREGA", "22/11/2026 a las 23:59", 3)],
    ]
    assert guia_pdf.fecha_entrega_texto(None) == "La indicada en la tarea de Moodle UTA"


def test_secciones_numeradas_en_romano_del_formulario_uta():
    import inspect
    fuente = inspect.getsource(guia_pdf.renderizar_pdf)
    assert re.findall(r'_seccion\(pdf, "([^"]+)"', fuente) == [
        "I. TEMA:", "II. OBJETIVO:", "III. MODALIDAD Y DURACIÓN:", "IV. INSTRUCCIONES:", "V. MATERIAL Y RECURSOS:",
        "VI. FUNDAMENTACIÓN Y EJEMPLO RESUELTO:", "VII. ACTIVIDADES POR DESARROLLAR:"]
    for excluido in ("firma", "Firma", "BIBLIOGRAF", "Coordinador", "VALIDACI", "Diagnóstico"):
        assert excluido not in fuente + inspect.getsource(guia_pdf._GuiaPDF)


def test_tema_objetivo_y_modalidad():
    guia = _guia()
    assert guia["objetivo"] == ("Diseñar jerarquías de clases con herencia, clases abstractas y polimorfismo, "
                                "reutilizando código sin romper la relación «es un».")
    assert (guia["modalidad"], guia["duracion"]) == ("Presencial", "2 horas")


@pytest.mark.parametrize("sigla", sorted(ca.CONTENIDOS))
def test_cada_materia_tiene_objetivo_en_infinitivo_y_entorno(sigla):
    assert sorted(ca.OBJETIVOS[sigla]) == _UNIDADES[sigla]
    for objetivo in ca.OBJETIVOS[sigla].values():
        assert not objetivo.endswith(".") and re.match(r"^[A-ZÁÉÍÓÚ][a-záéíóúñ]+(ar|er|ir)\b", objetivo), objetivo
        assert "falencias" not in objetivo
    assert ca.ENTORNOS[sigla]


@pytest.mark.parametrize("sigla", sorted(ca.CONTENIDOS))
def test_textos_sin_marcas_que_alteren_el_formato(sigla):
    # Las negritas (**) las agrega el generador; el código va entre pares de acentos graves
    textos = [t for u in ca.CONTENIDOS[sigla].values() for par in u["temas"] for t in par]
    textos += [t for fuentes in ca.RECURSOS[sigla].values() for par in fuentes for t in par]
    textos += [ca.ENTORNOS[sigla], *ca.OBJETIVOS[sigla].values()]
    for texto in textos:
        assert "**" not in texto and texto.count("`") % 2 == 0, texto


def test_material_al_grano_un_ejemplo_y_hasta_tres_ejercicios():
    guia = _guia()
    assert [t for t, _ in guia["temas"]] == ["Herencia", "Sobrescritura y clases abstractas", "Polimorfismo"]
    assert all(len(explicacion) <= 260 for _, explicacion in guia["temas"])        # explicaciones breves
    assert guia["ejemplo"]["enunciado"] and 3 <= len(guia["ejemplo"]["pasos"]) <= 5
    assert 2 <= len(guia["ejercicios"]) <= 3


@pytest.mark.parametrize("sigla", sorted(ca.CONTENIDOS))
def test_simbolos_ascii_limpios_en_ejemplos_y_ejercicios(sigla):
    for unidad in ca.CONTENIDOS[sigla].values():
        textos = [unidad["ejemplo"]["enunciado"], unidad["ejemplo"]["resultado"], *unidad["ejemplo"]["pasos"],
                  *unidad["ejercicios"]]
        for texto in textos:
            assert "->" not in texto, texto                                     # flechas limpias (=>)
            assert not re.search(r"«[^»]*[\[\](){}+*/=<>\d][^»]*»", texto), texto   # fórmulas sin comillas angulares
            # El código va entre acentos graves (Courier, sin comillas): ninguna comilla simple pegada a símbolos
            assert "'" not in texto and texto.count("`") % 2 == 0, texto
            assert "\\prime" not in texto and "^{" not in texto, texto
            guia_pdf._texto(texto.replace("`", "")).encode("latin-1", "strict")


def test_el_codigo_se_imprime_en_courier_sin_comillas_ni_acentos_graves(monkeypatch):
    escritos = []

    class Registro:
        def set_font(self, familia, estilo="", tam=0):
            self.familia = familia

        def write(self, alto, texto):
            escritos.append((self.familia, texto))

        def ln(self, alto):
            pass

    guia_pdf._escribir(Registro(), "Evalúe la expresión postfija `5 3 + 2 *` usando una **pila**.")
    assert escritos == [("helvetica", "Evalúe la expresión postfija "), ("courier", "5 3 + 2 *"),
                        ("helvetica", " usando una "), ("helvetica", "pila"), ("helvetica", ".")]


def test_catalogo_incluye_las_materias_de_ambos_docentes():
    assert set(ca.CONTENIDOS) == {"POO", "ED", "MA", "MCS", "IS1", "BDA", "DW", "CAL"}
    assert ca.contenido_unidad("SOF-BDA-B", 1)["titulo"] == "Modelo relacional y normalización"


@pytest.mark.parametrize("sigla", sorted(ca.CONTENIDOS))
def test_cada_guia_del_catalogo_ocupa_como_maximo_dos_paginas(sigla):
    assert sorted(ca.CONTENIDOS[sigla]) == _UNIDADES[sigla]
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


def test_sin_registro_omite_las_notas_y_tolera_texto_fuera_de_latin1():
    guia = _guia(registro=None, titulo="Refuerzo — «U2» → ≥ 7")
    assert guia["motivo"] is None and guia["instrucciones_intro"].startswith("Carlos, este refuerzo corresponde a la Unidad 2 (")
    assert guia["instrucciones_pasos"][0].startswith("**Motivo académico:** reforzar los contenidos")
    assert renderizar_pdf(guia).startswith(b"%PDF-")


def test_el_titulo_muestra_la_materia_y_no_el_codigo_del_curso():
    guia = _guia(titulo="Refuerzo: Refuerzo Didáctico Guiado (Unidad 2) — SOF-POO-A")
    assert guia["titulo"] == "Refuerzo: Refuerzo Didáctico Guiado (Unidad 2) — Programación orientada a objetos — Paralelo A"
