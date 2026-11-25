"""
Guía de refuerzo académico en PDF con el formato institucional de las guías prácticas / tareas de la
Universidad Técnica de Ambato (FISEI), adaptado a una actividad de refuerzo individual.

Se genera al aprobar y publicar un refuerzo y se adjunta a la tarea de Moodle (plugin local_edumonitor).
Estructura (1 a 2 páginas): cabecera con el escudo UTA, tabla de datos generales y secciones numeradas
I. Tema · II. Objetivo · III. Modalidad y duración · IV. Diagnóstico (4 tarjetas) · V. Instrucciones del docente ·
VI. Recursos · VII. Fundamentación y ejemplo resuelto · VIII. Actividades por desarrollar · IX. Resultados esperados.
Sin tabla bibliográfica extensa, sin cuadro de firmas y sin rúbrica.
`construir_guia` arma el contenido sólo con datos reales y el catálogo de la materia; `renderizar_pdf` lo dibuja.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fpdf import FPDF, FontFace

from app.services.contenidos_academicos import (contenido_unidad, entorno_materia, habilidad_materia,
                                                 objetivo_unidad, recursos_unidad, sigla_curso)

LOGO = Path(__file__).resolve().parent.parent / "recursos" / "uta-logo-azul.png"
AZUL = (0, 47, 108)
DORADO = (197, 155, 39)
GRIS = (90, 98, 110)
TEXTO = (30, 34, 40)
FONDO = (241, 244, 249)
BORDE = (214, 222, 234)
LINEA_TABLA = (150, 160, 175)

UNIVERSIDAD = "UNIVERSIDAD TÉCNICA DE AMBATO"
SUBTITULO = "GUÍA DE REFUERZO ACADÉMICO Y APLICACIÓN DE APRENDIZAJES"
FACULTAD = "Ingeniería en Sistemas, Electrónica e Industrial (FISEI)"
CARRERA = "Software"
NIVEL_CICLO = "Cuarto Semestre · Julio – Diciembre 2026"
MODALIDAD = "Virtual / Trabajo autónomo en Moodle UTA"
DURACION = "2 horas no presenciales"
PIE = "UTA - FISEI"

COMPONENTES = [("acd", "Exámenes"), ("tareas", "Tareas"), ("pae", "APE")]
NIVELES = {"CRITICO": "Crítico", "EN_RIESGO": "En riesgo", "ACEPTABLE": "Aceptable"}
MAX_TEMAS, MAX_PASOS, MAX_EJERCICIOS, MAX_ACTIVIDADES = 3, 5, 3, 3
_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]

# fpdf2 con fuentes estándar usa Latin-1: se sustituyen los pocos signos tipográficos que no lo admiten
_SUSTITUTOS = {"—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "•": "-", "≥": ">=",
               "≤": "<=", "→": "=>", "->": "=>", "←": "<=", "²": "^2", " ": " "}


def _texto(valor: Any) -> str:
    texto = "" if valor is None else str(valor)
    for origen, destino in _SUSTITUTOS.items():
        texto = texto.replace(origen, destino)
    return texto.encode("latin-1", "replace").decode("latin-1")


def _numero_unidad(unidad: Optional[str]) -> int:
    digitos = "".join(ch for ch in str(unidad or "") if ch.isdigit())
    return int(digitos) if digitos else 1


def _materia(fullname: str, shortname: str) -> str:
    """'(SOF) ESTRUCTURA DE DATOS - B' -> 'Estructura de datos — Paralelo B' (con tildes habituales)."""
    from app.services.agente_herramientas import _nombre_curso  # evita importación circular
    return _nombre_curso(fullname or shortname).replace(", paralelo", " — Paralelo")


def fecha_larga(fecha: Optional[datetime]) -> str:
    """datetime(2026, 12, 2, 23, 59) -> 'miércoles 2 de diciembre de 2026, 23:59'."""
    if not fecha:
        return "La indicada en la tarea de Moodle UTA"
    return (f"{_DIAS[fecha.weekday()]} {fecha.day} de {_MESES[fecha.month - 1]} de {fecha.year}, "
            f"{fecha.strftime('%H:%M')}")


def _detalle_actividad(a: Dict[str, Any]) -> str:
    if a.get("estado") == "SIN_ENTREGA":
        return f"{a.get('id_number')} (sin entrega)"
    if a.get("estado") == "PENDIENTE" or a.get("nota") is None:
        return f"{a.get('id_number')} (pendiente)"
    return f"{a.get('id_number')} ({a['nota']:.2f})"


def _diagnostico(registro: Dict[str, Any], numero: int, debiles: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """4 tarjetas métricas (etiqueta, valor): nota de la unidad, nota ponderada y estado, componente y actividades."""
    nota_unidad = (registro.get("promedios_unidad") or {}).get(f"U{numero}")
    final = registro.get("nota_final")
    nivel = NIVELES.get(registro.get("nivel_riesgo"), registro.get("nivel_riesgo") or "-")
    componentes = [(nombre, registro.get(clave)) for clave, nombre in COMPONENTES if registro.get(clave) is not None]
    componente = min(componentes, key=lambda c: c[1]) if componentes else None
    return [
        (f"Nota de la Unidad {numero}", f"{nota_unidad:.2f} / 10" if nota_unidad is not None else "Sin notas aún"),
        ("Nota ponderada y estado", f"{final:.2f} / 10 (Nivel: {nivel})" if final is not None else "-"),
        ("Componente a reforzar", f"{componente[0]} ({componente[1]:.2f} / 10)" if componente else "-"),
        ("Actividades a repasar", ", ".join(_detalle_actividad(a) for a in debiles) if debiles else "Ninguna pendiente"),
    ]


def _lista(items: List[str]) -> str:
    """['a', 'b', 'c'] -> 'a, b y c'."""
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1] if items else ""


def _en_minuscula(subtemas: List[str]) -> List[str]:
    """Subtemas a mitad de frase en minúscula, salvo siglas («SQL avanzado», «HTML y CSS»)."""
    return [t if len(t) > 1 and t[1].isupper() else t[:1].lower() + t[1:] for t in subtemas]


def indicaciones_estudiante(nombres: str, numero: int, titulo_unidad: str, subtemas: List[str],
                            fecha_entrega: Optional[datetime] = None) -> str:
    """Mensaje cercano del profesor al estudiante, que nombra los subtemas de la unidad a fortalecer."""
    nombre = (nombres or "").split()[0] if nombres else ""
    plazo = (f"hasta el {fecha_entrega.strftime('%d/%m/%Y')} a las {fecha_entrega.strftime('%H:%M')}"
             if fecha_entrega else "hasta la fecha indicada en la tarea")
    temas = _lista(_en_minuscula(subtemas))
    return (f"Hola {nombre}, revisando tus calificaciones de la Unidad {numero} ({titulo_unidad}), te comparto esta "
            f"guía de apoyo para fortalecer {temas} antes de tu actividad de recuperación. Revisa primero la "
            "fundamentación y el material recomendado, analiza el ejemplo paso a paso, resuelve los ejercicios de la "
            f"sección VIII y sube tu archivo (PDF o código) en la tarea de Moodle UTA {plazo}.")


# Textos que no escribió el docente: borradores en tercera persona («El estudiante X presenta dificultades...») o
# mensajes generados por versiones anteriores de la guía. Se reemplazan por el mensaje actual.
_TEXTO_GENERADO = re.compile(r"^\s*((el|la) (estudiante|alumn[oa])\b|estimado/a \S+, se ha identificado|"
                             r"hola \S+, revisando tus calificaciones)", re.IGNORECASE)


def _indicaciones(instrucciones: str, generadas: str) -> str:
    """Indicaciones al estudiante: el mensaje del profesor con los subtemas y, si las hay, sus observaciones."""
    texto = (instrucciones or "").strip()
    if not texto or _TEXTO_GENERADO.match(texto):
        return generadas
    if texto.lower().startswith(("estimado", "estimada", "hola")):
        return texto   # el docente ya le escribió directamente al estudiante
    return f"{generadas}\n\nObservación de tu docente: {texto}"


def _resultados(subtemas: List[str], numero: int, habilidad: str) -> List[str]:
    """IX. Lo que el estudiante demostrará al completar la tarea de refuerzo."""
    return [
        f"**Dominio conceptual:** explica y aplica {_lista(_en_minuscula(subtemas))} (Unidad {numero}).",
        f"**Resolución de problemas:** capacidad para {habilidad}.",
        "**Pensamiento crítico y responsabilidad académica:** analiza sus errores de la evaluación, los corrige con "
        "autonomía y entrega su trabajo a tiempo en Moodle UTA.",
    ]


def construir_guia(*, estudiante: Dict[str, Any], curso: Dict[str, Any], unidad: Optional[str],
                   docente: str, titulo: str, instrucciones: str, fecha_entrega: Optional[datetime],
                   registro: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Contenido de la guía. `registro` es el registro analítico del estudiante en el curso (sincronización):
    notas por unidad, componentes y actividades; si falta, la guía omite el diagnóstico numérico.
    """
    numero = _numero_unidad(unidad)
    shortname = curso.get("shortname", "")
    contenido = contenido_unidad(shortname, numero)
    registro = registro or {}
    todas = registro.get("actividades") or []
    de_la_unidad = [a for a in todas if a.get("unidad") in (None, f"U{numero}", numero)] or todas
    debiles = sorted(
        (a for a in de_la_unidad
         if a.get("estado") in ("SIN_ENTREGA", "PENDIENTE") or (a.get("nota") is not None and a["nota"] < 7)),
        key=lambda a: (a.get("nota") is not None, a.get("nota") or 0))[:MAX_ACTIVIDADES]

    if not contenido:  # materia fuera del catálogo: guía breve basada en sus actividades
        contenido = {
            "titulo": f"Unidad {numero}",
            "temas": [(a.get("nombre") or a.get("id_number"),
                       "Repase el material de clase de esta actividad y anote sus dudas para la tutoría.")
                      for a in debiles] or [("Repaso de la unidad", "Repase el material de clase y los ejercicios hechos en clase.")],
            "ejemplo": None,
            "ejercicios": [f"Rehaga la actividad {a.get('id_number')} aplicando la retroalimentación del docente."
                           for a in debiles] or ["Resuelva nuevamente los ejercicios de la unidad."],
        }

    ejemplo = contenido.get("ejemplo")
    temas = contenido["temas"][:MAX_TEMAS]
    subtemas = [t for t, _ in temas]
    generadas = indicaciones_estudiante(estudiante.get("nombres") or "", numero, contenido["titulo"], subtemas,
                                        fecha_entrega)
    materia = _materia(curso.get("fullname", ""), shortname)
    objetivo = objetivo_unidad(shortname, numero) or f"Afianzar los contenidos de la Unidad {numero}"
    return {
        # En el PDF el estudiante ve el nombre de la materia, no el código interno del curso (SOF-ED-B)
        "titulo": titulo.replace(shortname, materia) if shortname else titulo,
        "estudiante": {"nombres": estudiante.get("nombres"), "cedula": estudiante.get("cedula"),
                       "email": estudiante.get("email"), "id_number": estudiante.get("id_number")},
        "materia": materia,
        "sigla": sigla_curso(shortname),
        "unidad": numero,
        "unidad_titulo": f"Unidad {numero}: {contenido['titulo']}",
        "subtemas": subtemas,
        "objetivo": f"{objetivo}, superando las falencias detectadas en la evaluación de la Unidad {numero}.",
        "modalidad": MODALIDAD,
        "duracion": DURACION,
        "docente": docente,
        "fecha_entrega": fecha_entrega,
        "instrucciones": (instrucciones or "").strip(),
        "indicaciones": _indicaciones(instrucciones, generadas),
        "diagnostico": _diagnostico(registro, numero, debiles) if registro else [],
        "temas": temas,
        "entorno": entorno_materia(shortname),
        "recursos": recursos_unidad(shortname, numero),
        "ejemplo": {**ejemplo, "pasos": ejemplo["pasos"][:MAX_PASOS]} if ejemplo else None,
        "ejercicios": contenido["ejercicios"][:MAX_EJERCICIOS],
        "resultados": _resultados(subtemas, numero, habilidad_materia(shortname)),
    }


def datos_generales(guia: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Tabla de datos generales de la cabecera institucional UTA (etiqueta, valor)."""
    est = guia["estudiante"]
    contacto = " · ".join(v for v in (f"C.I. {est['cedula']}" if est.get("cedula") else "", est.get("email")) if v)
    return [
        ("FACULTAD", FACULTAD),
        ("CARRERA", CARRERA),
        ("ASIGNATURA", guia["materia"].replace(" — ", " - ")),
        ("NIVEL / CICLO ACADÉMICO", NIVEL_CICLO),
        ("DOCENTE", guia["docente"] or "-"),
        ("ESTUDIANTE", f"{est.get('nombres') or '-'}" + (f" ({contacto})" if contacto else "")),
        ("FECHA LÍMITE DE ENTREGA", fecha_larga(guia.get("fecha_entrega"))),
    ]


def nombre_archivo(guia: Dict[str, Any]) -> str:
    """'Guia_refuerzo_POO_U2_U-04.pdf' (sin espacios ni tildes: se usa como nombre del adjunto en Moodle)."""
    return f"Guia_refuerzo_{guia['sigla']}_U{guia['unidad']}_{guia['estudiante'].get('id_number') or 'estudiante'}.pdf"


class _GuiaPDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            # Cabecera institucional: escudo UTA, nombre de la universidad y tipo de guía
            # El escudo incluye la marca nominativa: los títulos van centrados en el espacio a su derecha
            x_texto = 64 if LOGO.exists() else 15
            if LOGO.exists():
                self.image(str(LOGO), x=15, y=10, h=17)
            self.set_xy(x_texto, 12)
            self.set_font("helvetica", "B", 14.5)
            self.set_text_color(*AZUL)
            self.cell(195 - x_texto, 7, _texto(UNIVERSIDAD), align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_x(x_texto)
            self.set_font("helvetica", "B", 8.6)
            self.set_text_color(*GRIS)
            self.cell(195 - x_texto, 5, _texto(SUBTITULO), align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(*DORADO)
            self.set_line_width(0.7)
            self.line(15, 31, 195, 31)
            self.set_y(34)
            return
        if LOGO.exists():
            self.image(str(LOGO), x=15, y=8, h=9)
        self.set_xy(80, 9)
        self.set_font("helvetica", "B", 8.5)
        self.set_text_color(*AZUL)
        self.cell(115, 4, _texto("Universidad Técnica de Ambato · FISEI"), align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_x(80)
        self.set_font("helvetica", "", 7)
        self.set_text_color(*GRIS)
        self.cell(115, 3.5, _texto(SUBTITULO.capitalize()), align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*DORADO)
        self.set_line_width(0.5)
        self.line(15, 19, 195, 19)
        self.set_y(22)

    def footer(self):
        self.set_y(-12)
        self.set_font("helvetica", "", 7)
        self.set_text_color(*GRIS)
        self.cell(0, 6, _texto(f"Página {self.page_no()}/{{nb}} · {PIE}"), align="C")


def _titulo_seccion(pdf: FPDF, numero: str, texto: str) -> None:
    """Encabezado numerado en romano con una línea fina institucional debajo."""
    if pdf.get_y() > 258:
        pdf.add_page()
    pdf.ln(2)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 5.4, _texto(f"{numero}. {texto.upper()}"), new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y()
    pdf.set_draw_color(*BORDE)
    pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(1.2)
    pdf.set_text_color(*TEXTO)


def _parrafo(pdf: FPDF, texto: str, tam: float = 9.5, estilo: str = "", alto: float = 4.5,
             markdown: bool = False) -> None:
    pdf.set_font("helvetica", estilo, tam)
    pdf.multi_cell(0, alto, _texto(texto), markdown=markdown, new_x="LMARGIN", new_y="NEXT")


def _tarjetas(pdf: FPDF, tarjetas: List[Tuple[str, str]]) -> None:
    """Cuadrícula 2x2 de tarjetas métricas con borde suave: etiqueta pequeña y valor destacado."""
    ancho, alto, sep = 88.5, 14, 2.5
    x0 = pdf.l_margin
    for i, (etiqueta, valor) in enumerate(tarjetas):
        if i % 2 == 0:
            if i:
                pdf.set_y(y + alto + sep)
            y = pdf.get_y()
        x = x0 + (i % 2) * (ancho + sep)
        pdf.set_fill_color(*FONDO)
        pdf.set_draw_color(*BORDE)
        pdf.set_line_width(0.3)
        pdf.rect(x, y, ancho, alto, style="DF", round_corners=True, corner_radius=2)
        pdf.set_xy(x + 3.5, y + 2)
        pdf.set_font("helvetica", "", 7.5)
        pdf.set_text_color(*GRIS)
        pdf.cell(ancho - 7, 4, _texto(etiqueta.upper()))
        pdf.set_xy(x + 3.5, y + 6.8)
        largo = len(valor) > 34
        pdf.set_font("helvetica", "B", 8.8 if largo else 11)
        pdf.set_text_color(*AZUL)
        pdf.multi_cell(ancho - 7, 3.9 if largo else 6, _texto(valor), max_line_height=4)
    pdf.set_y(y + alto + 1)
    pdf.set_text_color(*TEXTO)


def _vinieta(pdf: FPDF, marca: str, texto: str, markdown: bool = False) -> None:
    """Viñeta con sangría francesa: las líneas siguientes quedan alineadas con el texto, no con el margen."""
    pdf.set_font("helvetica", "B", 9.5)
    pdf.cell(6, 4.5, _texto(marca))
    pdf.set_font("helvetica", "", 9.5)
    pdf.multi_cell(0, 4.5, _texto(texto), markdown=markdown, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(0.4)


def _tabla_datos(pdf: FPDF, filas: List[Tuple[str, str]]) -> None:
    """Tabla de datos generales en 2 columnas con bordes finos institucionales."""
    pdf.set_draw_color(*LINEA_TABLA)
    pdf.set_line_width(0.2)
    pdf.set_text_color(*TEXTO)
    pdf.set_font("helvetica", "", 8.5)
    etiqueta = FontFace(emphasis="BOLD", color=AZUL, size_pt=7.8, fill_color=FONDO)
    valor = FontFace(size_pt=8.5)
    with pdf.table(col_widths=(52, 128), line_height=4.6, text_align="LEFT", borders_layout="ALL",
                   first_row_as_headings=False, padding=(1.1, 2)) as tabla:
        for e, v in filas:
            fila = tabla.row()
            fila.cell(_texto(e), style=etiqueta)
            fila.cell(_texto(v), style=valor)


def renderizar_pdf(guia: Dict[str, Any]) -> bytes:
    pdf = _GuiaPDF(format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(True, margin=15)
    pdf.set_title(_texto(f"Guía de refuerzo académico - {guia['titulo']}"))
    pdf.set_author("Universidad Técnica de Ambato · FISEI")
    pdf.set_creator("Universidad Técnica de Ambato · FISEI")
    pdf.alias_nb_pages()
    pdf.add_page()

    _tabla_datos(pdf, datos_generales(guia))

    _titulo_seccion(pdf, "I", "Tema")
    _parrafo(pdf, guia["unidad_titulo"], estilo="B")
    if guia.get("subtemas"):
        _parrafo(pdf, f"**Subtemas a reforzar:** {_lista(guia['subtemas'])}.", markdown=True)

    _titulo_seccion(pdf, "II", "Objetivo")
    _parrafo(pdf, guia["objetivo"])

    _titulo_seccion(pdf, "III", "Modalidad y duración")
    _parrafo(pdf, f"**Modalidad:** {guia['modalidad']}   ·   **Duración estimada:** {guia['duracion']}",
             markdown=True)

    if guia.get("diagnostico"):
        _titulo_seccion(pdf, "IV", "Diagnóstico académico del estudiante")
        pdf.ln(0.3)
        _tarjetas(pdf, guia["diagnostico"])

    _titulo_seccion(pdf, "V", "Instrucciones y orientación del docente")
    _parrafo(pdf, guia["indicaciones"])

    _titulo_seccion(pdf, "VI", "Recursos y material de apoyo")
    _vinieta(pdf, "-", f"**Entorno de trabajo:** {guia['entorno']}.", markdown=True)
    recursos = guia.get("recursos") or []
    aula = [r for r in recursos if r[0].startswith("Aula virtual")]
    for fuente, detalle in aula + [r for r in recursos if r not in aula]:
        _vinieta(pdf, "-", f"**{fuente}:** {detalle}", markdown=True)

    _titulo_seccion(pdf, "VII", "Fundamentación y ejemplo resuelto")
    for tema, explicacion in guia["temas"]:
        _parrafo(pdf, f"**{tema}:** {explicacion}", markdown=True)
        pdf.ln(0.8)
    ejemplo = guia.get("ejemplo")
    if ejemplo:
        if pdf.get_y() > 245:   # el ejemplo no empieza al pie de la página, separado de sus pasos
            pdf.add_page()
        pdf.ln(0.6)
        pdf.set_font("helvetica", "B", 9.5)
        pdf.set_text_color(*AZUL)
        pdf.cell(0, 5, _texto("Ejemplo resuelto paso a paso"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*TEXTO)
        _parrafo(pdf, ejemplo["enunciado"], estilo="I")
        pdf.ln(0.8)
        for i, paso in enumerate(ejemplo["pasos"], 1):
            _vinieta(pdf, f"{i}.", paso)
        pdf.set_fill_color(*FONDO)
        pdf.set_font("helvetica", "B", 9)
        pdf.multi_cell(0, 5.5, _texto(f"Resultado: {ejemplo['resultado']}"), fill=True, new_x="LMARGIN", new_y="NEXT")

    _titulo_seccion(pdf, "VIII", "Actividades por desarrollar (ejercicios de práctica)")
    _parrafo(pdf, "Resuelve los siguientes ejercicios y súbelos como tarea de refuerzo en Moodle UTA:", tam=9,
             estilo="I")
    pdf.ln(0.6)
    for i, ejercicio in enumerate(guia["ejercicios"], 1):
        _vinieta(pdf, f"{i}.", ejercicio)

    _titulo_seccion(pdf, "IX", "Resultados esperados y habilidades")
    for resultado in guia["resultados"]:
        _vinieta(pdf, "-", resultado, markdown=True)

    return bytes(pdf.output())


def generar_guia_pdf(**datos: Any) -> Dict[str, Any]:
    """Atajo: construye la guía y devuelve {'guia', 'nombre', 'pdf'}."""
    guia = construir_guia(**datos)
    return {"guia": guia, "nombre": nombre_archivo(guia), "pdf": renderizar_pdf(guia)}
