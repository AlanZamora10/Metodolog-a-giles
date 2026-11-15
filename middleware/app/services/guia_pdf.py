"""
Guía de estudio institucional en PDF para un refuerzo académico (UTA · FISEI).

Se genera al aprobar y publicar un refuerzo y se adjunta a la tarea de Moodle (plugin local_edumonitor).
`construir_guia` arma el contenido sólo con datos reales del estudiante y el catálogo de contenidos de la
materia; `renderizar_pdf` lo dibuja con fpdf2. Ambas funciones son puras (fáciles de probar).
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fpdf import FPDF, FontFace

from app.services.contenidos_academicos import contenido_unidad, sigla_curso

LOGO = Path(__file__).resolve().parent.parent / "recursos" / "uta-logo-azul.png"
AZUL = (0, 47, 108)
DORADO = (197, 155, 39)
GRIS = (90, 98, 110)
FONDO = (241, 244, 249)

COMPONENTES = [("acd", "Exámenes", 40), ("tareas", "Tareas", 30), ("pae", "APE", 30)]
NIVELES = {"CRITICO": "crítico", "EN_RIESGO": "en riesgo", "ACEPTABLE": "aceptable"}

# Rúbrica de evaluación del refuerzo: los pesos suman 100 %
RUBRICA = [
    ("Comprensión conceptual", 25,
     "Explica los conceptos con precisión y ejemplos propios.",
     "Explica los conceptos con imprecisiones menores.",
     "Explicación incompleta o memorística.",
     "No explica los conceptos o son incorrectos."),
    ("Resolución de ejercicios", 40,
     "Resuelve todos los ejercicios correctamente y justifica cada paso.",
     "Resuelve la mayoría con errores menores.",
     "Resuelve la mitad o con errores de procedimiento.",
     "Resuelve menos de la mitad o sin procedimiento."),
    ("Aplicación y análisis", 20,
     "Aplica lo aprendido a casos nuevos y analiza los resultados.",
     "Aplica lo aprendido con apoyo del ejemplo resuelto.",
     "Aplicación parcial, sin análisis del resultado.",
     "No logra aplicar lo aprendido."),
    ("Presentación y puntualidad", 15,
     "Entrega a tiempo, ordenada y con buena redacción.",
     "Entrega a tiempo con detalles de formato.",
     "Entrega tardía o desordenada.",
     "No entrega o el trabajo es ilegible."),
]
NIVELES_RUBRICA = ("Excelente (100 %)", "Satisfactorio (75 %)", "En desarrollo (50 %)", "Insuficiente (25 %)")

# fpdf2 con fuentes estándar usa Latin-1: se sustituyen los pocos signos tipográficos que no lo admiten
_SUSTITUTOS = {"—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "•": "-", "≥": ">=",
               "≤": "<=", "→": "->", "←": "<-", "²": "^2", " ": " "}


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


def construir_guia(*, estudiante: Dict[str, Any], curso: Dict[str, Any], unidad: Optional[str],
                   docente: str, titulo: str, instrucciones: str, fecha_entrega: Optional[datetime],
                   registro: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Contenido de la guía. `registro` es el registro analítico del estudiante en el curso (sincronización):
    nota ponderada, componentes y actividades; si falta, la guía omite el diagnóstico numérico.
    """
    numero = _numero_unidad(unidad)
    contenido = contenido_unidad(curso.get("shortname", ""), numero)
    registro = registro or {}
    actividades = [a for a in registro.get("actividades") or [] if a.get("unidad") in (None, f"U{numero}", numero)]
    debiles = sorted(
        (a for a in (actividades or registro.get("actividades") or [])
         if a.get("estado") in ("SIN_ENTREGA", "PENDIENTE") or (a.get("nota") is not None and a["nota"] < 7)),
        key=lambda a: (a.get("nota") is not None, a.get("nota") or 0))[:6]

    if not contenido:  # materia fuera del catálogo: guía de estudio genérica basada en sus actividades
        contenido = {
            "titulo": f"Unidad {numero}",
            "temas": [(a.get("nombre") or a.get("id_number"),
                       "Revise el material de clase de la unidad y los apuntes de esta actividad; identifique los "
                       "conceptos que no domina y anote sus dudas para la tutoría.") for a in debiles[:3]]
            or [("Repaso de la unidad", "Revise el material de clase y los ejercicios resueltos en clase.")],
            "ejemplo": None,
            "ejercicios": [f"Rehaga la actividad {a.get('id_number')} aplicando la retroalimentación del docente."
                           for a in debiles[:4]] or ["Resuelva nuevamente los ejercicios de la unidad."],
        }

    return {
        "titulo": titulo,
        "estudiante": {"nombres": estudiante.get("nombres"), "cedula": estudiante.get("cedula"),
                       "email": estudiante.get("email"), "id_number": estudiante.get("id_number")},
        "materia": _materia(curso.get("fullname", ""), curso.get("shortname", "")),
        "sigla": sigla_curso(curso.get("shortname", "")),
        "unidad": numero,
        "unidad_titulo": f"Unidad {numero}: {contenido['titulo']}",
        "docente": docente,
        "fecha_entrega": fecha_entrega,
        "instrucciones": (instrucciones or "").strip(),
        "diagnostico": {
            "nota_final": registro.get("nota_final"),
            "nivel": NIVELES.get(registro.get("nivel_riesgo"), registro.get("nivel_riesgo")),
            "componentes": [(nombre, peso, registro.get(clave)) for clave, nombre, peso in COMPONENTES],
            "actividades": [(a.get("id_number"), a.get("nombre"), a.get("nota"), a.get("estado")) for a in debiles],
        } if registro else None,
        "temas": contenido["temas"],
        "ejemplo": contenido.get("ejemplo"),
        "ejercicios": contenido["ejercicios"],
        "rubrica": RUBRICA,
    }


def nombre_archivo(guia: Dict[str, Any]) -> str:
    """'Guia_refuerzo_POO_U2_U-04.pdf' (sin espacios ni tildes: se usa como nombre del adjunto en Moodle)."""
    return f"Guia_refuerzo_{guia['sigla']}_U{guia['unidad']}_{guia['estudiante'].get('id_number') or 'estudiante'}.pdf"


class _GuiaPDF(FPDF):
    def header(self):
        if LOGO.exists():
            self.image(str(LOGO), x=15, y=10, h=15)
        self.set_xy(80, 11)
        self.set_font("helvetica", "B", 12)
        self.set_text_color(*AZUL)
        self.cell(115, 6, _texto("Universidad Técnica de Ambato · FISEI"), align="R",
                  new_x="LMARGIN", new_y="NEXT")
        self.set_x(80)
        self.set_font("helvetica", "", 8)
        self.set_text_color(*GRIS)
        self.cell(115, 5, _texto("Facultad de Ingeniería en Sistemas, Electrónica e Industrial"), align="R",
                  new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*DORADO)
        self.set_line_width(0.8)
        self.line(15, 29, 195, 29)
        self.set_y(34)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(220, 225, 232)
        self.set_line_width(0.2)
        self.line(15, self.get_y(), 195, self.get_y())
        self.set_font("helvetica", "", 7.5)
        self.set_text_color(*GRIS)
        self.cell(0, 8, _texto(f"EduMonitor AI · Guía de estudio personalizada · Página {self.page_no()}/{{nb}}"),
                  align="C")


def _titulo_seccion(pdf: FPDF, numero: int, texto: str) -> None:
    if pdf.get_y() > 250:
        pdf.add_page()
    pdf.ln(3)
    pdf.set_font("helvetica", "B", 11.5)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 7, _texto(f"{numero}. {texto}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*AZUL)
    pdf.set_line_width(0.3)
    pdf.line(15, pdf.get_y(), 60, pdf.get_y())
    pdf.ln(2)
    pdf.set_text_color(30, 34, 40)


def _parrafo(pdf: FPDF, texto: str, tam: float = 9.5, estilo: str = "") -> None:
    pdf.set_font("helvetica", estilo, tam)
    pdf.multi_cell(0, 5, _texto(texto), new_x="LMARGIN", new_y="NEXT")


def _vinieta(pdf: FPDF, marca: str, texto: str) -> None:
    pdf.set_font("helvetica", "B", 9.5)
    pdf.cell(8, 5, _texto(marca))
    pdf.set_font("helvetica", "", 9.5)
    pdf.multi_cell(0, 5, _texto(texto), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(0.8)


def renderizar_pdf(guia: Dict[str, Any]) -> bytes:
    pdf = _GuiaPDF(format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(True, margin=18)
    pdf.set_title(_texto(f"Guía de estudio - {guia['titulo']}"))
    pdf.set_author("Universidad Técnica de Ambato · FISEI")
    pdf.set_creator("EduMonitor AI")
    pdf.alias_nb_pages()
    pdf.add_page()

    # Título
    pdf.set_font("helvetica", "B", 15)
    pdf.set_text_color(*AZUL)
    pdf.multi_cell(0, 7, _texto("Guía de estudio · Refuerzo académico"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 10.5)
    pdf.set_text_color(*GRIS)
    pdf.multi_cell(0, 5.5, _texto(guia["titulo"]), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Datos del estudiante
    est = guia["estudiante"]
    entrega = guia["fecha_entrega"].strftime("%d/%m/%Y %H:%M") if guia.get("fecha_entrega") else "Según Moodle"
    datos = [("Estudiante", est.get("nombres")), ("Cédula", est.get("cedula") or "No registrada"),
             ("Correo institucional", est.get("email")), ("Materia", guia["materia"]),
             ("Unidad con falencia", guia["unidad_titulo"]), ("Docente", guia["docente"]),
             ("Fecha de entrega", entrega), ("Período académico", "Julio a Diciembre 2026")]
    pdf.set_fill_color(*FONDO)
    pdf.set_text_color(30, 34, 40)
    with pdf.table(col_widths=(42, 138), line_height=6, borders_layout="NONE", cell_fill_color=FONDO,
                   cell_fill_mode="ALL", first_row_as_headings=False, padding=(1.2, 3)) as tabla:
        for etiqueta, valor in datos:
            fila = tabla.row()
            fila.cell(_texto(etiqueta), style=FontFace(emphasis="BOLD", color=AZUL, size_pt=9))
            fila.cell(_texto(valor), style=FontFace(size_pt=9))

    seccion = 1
    diag = guia.get("diagnostico")
    if diag:
        _titulo_seccion(pdf, seccion, "Diagnóstico de su rendimiento")
        seccion += 1
        nota = diag.get("nota_final")
        _parrafo(pdf, f"Nota ponderada actual en la materia: {nota:.2f}/10 (nivel {diag.get('nivel')})."
                 if nota is not None else "Nota ponderada actual: sin calificaciones registradas.")
        pdf.ln(1)
        pdf.set_font("helvetica", "", 9)
        with pdf.table(col_widths=(60, 30, 40), width=130, align="LEFT", line_height=6, text_align="CENTER",
                       headings_style=FontFace(emphasis="BOLD", color=255, fill_color=AZUL, size_pt=9)) as tabla:
            cab = tabla.row()
            for t in ("Componente", "Peso", "Promedio"):
                cab.cell(t)
            for nombre, peso, valor in diag["componentes"]:
                fila = tabla.row()
                fila.cell(_texto(nombre), style=FontFace(size_pt=9))
                fila.cell(f"{peso} %", style=FontFace(size_pt=9))
                fila.cell("-" if valor is None else f"{valor:.2f}/10", style=FontFace(size_pt=9))
        if diag["actividades"]:
            pdf.ln(2)
            _parrafo(pdf, "Actividades que debe reforzar:", estilo="B")
            for codigo, nombre, nota_act, estado in diag["actividades"]:
                detalle = ("sin entrega" if estado == "SIN_ENTREGA" else "pendiente de calificación"
                           if estado == "PENDIENTE" else f"{nota_act:.2f}/10")
                _vinieta(pdf, "-", f"{codigo} {nombre or ''}: {detalle}")

    if guia.get("instrucciones"):
        _titulo_seccion(pdf, seccion, "Indicaciones del docente")
        seccion += 1
        _parrafo(pdf, guia["instrucciones"])

    _titulo_seccion(pdf, seccion, "Explicación conceptual de los temas a reforzar")
    seccion += 1
    for i, (tema, explicacion) in enumerate(guia["temas"], 1):
        _parrafo(pdf, f"{guia['unidad']}.{i} {tema}", tam=10, estilo="B")
        _parrafo(pdf, explicacion)
        pdf.ln(1.5)

    ejemplo = guia.get("ejemplo")
    if ejemplo:
        _titulo_seccion(pdf, seccion, "Ejemplo resuelto paso a paso")
        seccion += 1
        _parrafo(pdf, f"Enunciado: {ejemplo['enunciado']}", estilo="I")
        pdf.ln(1)
        for i, paso in enumerate(ejemplo["pasos"], 1):
            _vinieta(pdf, f"{i}.", paso)
        pdf.set_fill_color(*FONDO)
        pdf.set_font("helvetica", "B", 9.5)
        pdf.multi_cell(0, 6, _texto(f"Resultado: {ejemplo['resultado']}"), fill=True, new_x="LMARGIN", new_y="NEXT")

    _titulo_seccion(pdf, seccion, "Ejercicios propuestos")
    seccion += 1
    for i, ejercicio in enumerate(guia["ejercicios"], 1):
        _vinieta(pdf, f"{i}.", ejercicio)
    _parrafo(pdf, "Suba su desarrollo (PDF, DOCX o ZIP) en esta misma tarea de Moodle UTA antes de la fecha de entrega.",
             tam=9, estilo="I")

    _titulo_seccion(pdf, seccion, "Rúbrica de evaluación (100 %)")
    estilo_cab = FontFace(emphasis="BOLD", color=255, fill_color=AZUL, size_pt=7.5)
    pdf.set_font("helvetica", "", 7.5)  # las celdas sin énfasis heredan la fuente actual
    with pdf.table(col_widths=(30, 13, 34, 34, 34, 35), line_height=4.2, text_align="LEFT",
                   headings_style=estilo_cab) as tabla:
        cab = tabla.row()
        for t in ("Criterio", "Peso", *NIVELES_RUBRICA):
            cab.cell(_texto(t))
        for criterio, peso, *descriptores in guia["rubrica"]:
            fila = tabla.row()
            fila.cell(_texto(criterio), style=FontFace(emphasis="BOLD", size_pt=7.5))
            fila.cell(f"{peso} %", style=FontFace(size_pt=7.5))
            for d in descriptores:
                fila.cell(_texto(d), style=FontFace(size_pt=7.5))
        total = tabla.row()
        total.cell("Total", style=FontFace(emphasis="BOLD", size_pt=7.5))
        total.cell(f"{sum(p for _, p, *_ in guia['rubrica'])} %", style=FontFace(emphasis="BOLD", size_pt=7.5))
        for _ in NIVELES_RUBRICA:
            total.cell("")
    pdf.ln(2)
    _parrafo(pdf, "Calificación = suma de (peso del criterio x porcentaje del nivel alcanzado), expresada sobre 10.",
             tam=8.5, estilo="I")

    return bytes(pdf.output())


def generar_guia_pdf(**datos: Any) -> Dict[str, Any]:
    """Atajo: construye la guía y devuelve {'guia', 'nombre', 'pdf'}."""
    guia = construir_guia(**datos)
    return {"guia": guia, "nombre": nombre_archivo(guia), "pdf": renderizar_pdf(guia)}
