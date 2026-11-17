"""
Guía de estudio en PDF para un refuerzo académico (UTA · FISEI): material de apoyo breve y práctico.

Se genera al aprobar y publicar un refuerzo y se adjunta a la tarea de Moodle (plugin local_edumonitor).
Contenido (1 a 2 páginas): datos del estudiante, diagnóstico puntual, indicaciones del docente, conceptos clave
de la unidad, un ejemplo resuelto y 2-3 ejercicios cortos. No es una hoja de calificación (sin rúbrica).
`construir_guia` arma el contenido sólo con datos reales y el catálogo de la materia; `renderizar_pdf` lo dibuja.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fpdf import FPDF, FontFace

from app.services.contenidos_academicos import contenido_unidad, sigla_curso

LOGO = Path(__file__).resolve().parent.parent / "recursos" / "uta-logo-azul.png"
AZUL = (0, 47, 108)
DORADO = (197, 155, 39)
GRIS = (90, 98, 110)
TEXTO = (30, 34, 40)
FONDO = (241, 244, 249)

COMPONENTES = [("acd", "Exámenes"), ("tareas", "Tareas"), ("pae", "APE")]
NIVELES = {"CRITICO": "crítico", "EN_RIESGO": "en riesgo", "ACEPTABLE": "aceptable"}
MAX_TEMAS, MAX_PASOS, MAX_EJERCICIOS, MAX_ACTIVIDADES = 3, 5, 3, 3

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


def _diagnostico(registro: Dict[str, Any], numero: int, debiles: List[Dict[str, Any]]) -> List[str]:
    """2-3 líneas: nota actual de la unidad, componente a reforzar y actividades puntuales."""
    lineas = []
    nota_unidad = (registro.get("promedios_unidad") or {}).get(f"U{numero}")
    nota = nota_unidad if nota_unidad is not None else registro.get("nota_final")
    if nota is not None:
        nivel = NIVELES.get(registro.get("nivel_riesgo"), registro.get("nivel_riesgo"))
        lineas.append(f"Nota actual en la Unidad {numero}: {nota:.2f}/10"
                      + (f" (nota ponderada de la materia: {registro['nota_final']:.2f}/10, nivel {nivel})."
                         if nota_unidad is not None and registro.get("nota_final") is not None else "."))
    componentes = [(nombre, registro.get(clave)) for clave, nombre in COMPONENTES if registro.get(clave) is not None]
    if componentes:
        nombre, valor = min(componentes, key=lambda c: c[1])
        lineas.append(f"Componente que más necesita reforzar: {nombre} ({valor:.2f}/10).")
    if debiles:
        detalle = ", ".join(
            f"{a.get('id_number')} ({'sin entrega' if a.get('estado') == 'SIN_ENTREGA' else 'pendiente' if a.get('estado') == 'PENDIENTE' else format(a['nota'], '.2f')})"
            for a in debiles)
        lineas.append(f"Actividades a repasar: {detalle}.")
    return lineas


def construir_guia(*, estudiante: Dict[str, Any], curso: Dict[str, Any], unidad: Optional[str],
                   docente: str, titulo: str, instrucciones: str, fecha_entrega: Optional[datetime],
                   registro: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Contenido de la guía. `registro` es el registro analítico del estudiante en el curso (sincronización):
    notas por unidad, componentes y actividades; si falta, la guía omite el diagnóstico numérico.
    """
    numero = _numero_unidad(unidad)
    contenido = contenido_unidad(curso.get("shortname", ""), numero)
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
        "diagnostico": _diagnostico(registro, numero, debiles) if registro else [],
        "temas": contenido["temas"][:MAX_TEMAS],
        "ejemplo": {**ejemplo, "pasos": ejemplo["pasos"][:MAX_PASOS]} if ejemplo else None,
        "ejercicios": contenido["ejercicios"][:MAX_EJERCICIOS],
    }


def nombre_archivo(guia: Dict[str, Any]) -> str:
    """'Guia_refuerzo_POO_U2_U-04.pdf' (sin espacios ni tildes: se usa como nombre del adjunto en Moodle)."""
    return f"Guia_refuerzo_{guia['sigla']}_U{guia['unidad']}_{guia['estudiante'].get('id_number') or 'estudiante'}.pdf"


class _GuiaPDF(FPDF):
    def header(self):
        if LOGO.exists():
            self.image(str(LOGO), x=15, y=9, h=11)
        self.set_xy(80, 10)
        self.set_font("helvetica", "B", 10.5)
        self.set_text_color(*AZUL)
        self.cell(115, 5, _texto("Universidad Técnica de Ambato · FISEI"), align="R",
                  new_x="LMARGIN", new_y="NEXT")
        self.set_x(80)
        self.set_font("helvetica", "", 7.5)
        self.set_text_color(*GRIS)
        self.cell(115, 4, _texto("Guía de estudio · EduMonitor AI"), align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*DORADO)
        self.set_line_width(0.6)
        self.line(15, 23, 195, 23)
        self.set_y(27)

    def footer(self):
        self.set_y(-12)
        self.set_font("helvetica", "", 7)
        self.set_text_color(*GRIS)
        self.cell(0, 6, _texto(f"Página {self.page_no()}/{{nb}}"), align="C")


def _titulo_seccion(pdf: FPDF, texto: str) -> None:
    if pdf.get_y() > 262:
        pdf.add_page()
    pdf.ln(2.5)
    pdf.set_font("helvetica", "B", 10.5)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 6, _texto(texto), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*TEXTO)


def _parrafo(pdf: FPDF, texto: str, tam: float = 9.5, estilo: str = "", alto: float = 4.8) -> None:
    pdf.set_font("helvetica", estilo, tam)
    pdf.multi_cell(0, alto, _texto(texto), new_x="LMARGIN", new_y="NEXT")


def _vinieta(pdf: FPDF, marca: str, texto: str) -> None:
    pdf.set_font("helvetica", "B", 9.5)
    pdf.cell(6, 4.8, _texto(marca))
    pdf.set_font("helvetica", "", 9.5)
    pdf.multi_cell(0, 4.8, _texto(texto), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(0.6)


def renderizar_pdf(guia: Dict[str, Any]) -> bytes:
    pdf = _GuiaPDF(format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(True, margin=15)
    pdf.set_title(_texto(f"Guía de estudio - {guia['titulo']}"))
    pdf.set_author("Universidad Técnica de Ambato · FISEI")
    pdf.set_creator("EduMonitor AI")
    pdf.alias_nb_pages()
    pdf.add_page()

    # Título y entrega
    pdf.set_font("helvetica", "B", 13)
    pdf.set_text_color(*AZUL)
    pdf.multi_cell(0, 6, _texto(guia["titulo"]), new_x="LMARGIN", new_y="NEXT")
    if guia.get("fecha_entrega"):
        pdf.set_font("helvetica", "", 8.5)
        pdf.set_text_color(*GRIS)
        pdf.cell(0, 5, _texto(f"Entrega de la actividad de refuerzo: {guia['fecha_entrega'].strftime('%d/%m/%Y %H:%M')}"),
                 new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.5)

    # Datos esenciales del estudiante (dos columnas)
    est = guia["estudiante"]
    pares = [("Estudiante", est.get("nombres"), "Cédula", est.get("cedula") or "No registrada"),
             ("Correo", est.get("email"), "Materia", guia["materia"]),
             ("Unidad a reforzar", guia["unidad_titulo"], "Docente", guia["docente"])]
    pdf.set_font("helvetica", "", 8.5)
    pdf.set_text_color(*TEXTO)
    etiqueta = FontFace(emphasis="BOLD", color=AZUL, size_pt=8)
    valor = FontFace(size_pt=8.5)
    with pdf.table(col_widths=(31, 61, 17, 71), line_height=5, text_align="LEFT", borders_layout="NONE", cell_fill_color=FONDO,
                   cell_fill_mode="ALL", first_row_as_headings=False, padding=(1, 2)) as tabla:
        for e1, v1, e2, v2 in pares:
            fila = tabla.row()
            fila.cell(_texto(e1), style=etiqueta)
            fila.cell(_texto(v1), style=valor)
            fila.cell(_texto(e2), style=etiqueta)
            fila.cell(_texto(v2), style=valor)

    if guia.get("diagnostico"):
        _titulo_seccion(pdf, "Diagnóstico")
        for linea in guia["diagnostico"]:
            _vinieta(pdf, "-", linea)

    if guia.get("instrucciones"):
        _titulo_seccion(pdf, "Indicaciones del docente")
        _parrafo(pdf, guia["instrucciones"])

    _titulo_seccion(pdf, "Conceptos clave")
    for tema, explicacion in guia["temas"]:
        pdf.set_font("helvetica", "B", 9.5)
        pdf.write(4.8, _texto(f"{tema}: "))
        pdf.set_font("helvetica", "", 9.5)
        pdf.write(4.8, _texto(explicacion))
        pdf.ln(6)

    ejemplo = guia.get("ejemplo")
    if ejemplo:
        _titulo_seccion(pdf, "Ejemplo resuelto")
        _parrafo(pdf, ejemplo["enunciado"], estilo="I")
        pdf.ln(0.8)
        for i, paso in enumerate(ejemplo["pasos"], 1):
            _vinieta(pdf, f"{i}.", paso)
        pdf.set_fill_color(*FONDO)
        pdf.set_font("helvetica", "B", 9)
        pdf.multi_cell(0, 5.5, _texto(f"Resultado: {ejemplo['resultado']}"), fill=True, new_x="LMARGIN", new_y="NEXT")

    _titulo_seccion(pdf, "Ejercicios de práctica")
    for i, ejercicio in enumerate(guia["ejercicios"], 1):
        _vinieta(pdf, f"{i}.", ejercicio)

    return bytes(pdf.output())


def generar_guia_pdf(**datos: Any) -> Dict[str, Any]:
    """Atajo: construye la guía y devuelve {'guia', 'nombre', 'pdf'}."""
    guia = construir_guia(**datos)
    return {"guia": guia, "nombre": nombre_archivo(guia), "pdf": renderizar_pdf(guia)}
