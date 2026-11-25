"""
Guía de estudio en PDF para un refuerzo académico (UTA · FISEI): material de apoyo breve y práctico.

Se genera al aprobar y publicar un refuerzo y se adjunta a la tarea de Moodle (plugin local_edumonitor).
Contenido (1 a 2 páginas): datos del estudiante, diagnóstico en 4 tarjetas métricas, indicaciones dirigidas al
estudiante (con los subtemas de la unidad), conceptos clave, un ejemplo resuelto y 2-3 ejercicios cortos.
No es una hoja de calificación (sin rúbrica).
`construir_guia` arma el contenido sólo con datos reales y el catálogo de la materia; `renderizar_pdf` lo dibuja.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fpdf import FPDF, FontFace

from app.services.contenidos_academicos import contenido_unidad, recursos_unidad, sigla_curso

LOGO = Path(__file__).resolve().parent.parent / "recursos" / "uta-logo-azul.png"
AZUL = (0, 47, 108)
DORADO = (197, 155, 39)
GRIS = (90, 98, 110)
TEXTO = (30, 34, 40)
FONDO = (241, 244, 249)

COMPONENTES = [("acd", "Exámenes"), ("tareas", "Tareas"), ("pae", "APE")]
NIVELES = {"CRITICO": "Crítico", "EN_RIESGO": "En riesgo", "ACEPTABLE": "Aceptable"}
BORDE = (214, 222, 234)
MAX_TEMAS, MAX_PASOS, MAX_EJERCICIOS, MAX_ACTIVIDADES = 3, 5, 3, 3

# fpdf2 con fuentes estándar usa Latin-1: se sustituyen los pocos signos tipográficos que no lo admiten
_SUSTITUTOS = {"—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "•": "-", "≥": ">=",
               "≤": "<=", "→": "=>", "->": "=>", "←": "<=", "²": "^2", " ": " "}


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


def indicaciones_estudiante(nombres: str, numero: int, titulo_unidad: str, subtemas: List[str],
                            fecha_entrega: Optional[datetime] = None) -> str:
    """Mensaje cercano del profesor al estudiante, que nombra los subtemas de la unidad a fortalecer."""
    nombre = (nombres or "").split()[0] if nombres else ""
    plazo = f"hasta el {fecha_entrega.strftime('%d/%m/%Y')}" if fecha_entrega else "hasta la fecha indicada en la tarea"
    # Subtemas a mitad de frase en minúscula, salvo siglas («SQL avanzado», «HTML y CSS»)
    temas = _lista([t if len(t) > 1 and t[1].isupper() else t[:1].lower() + t[1:] for t in subtemas])
    return (f"Hola {nombre}, revisando tus calificaciones de la Unidad {numero} ({titulo_unidad}), te comparto esta "
            f"guía de apoyo para fortalecer {temas} antes de tu actividad de recuperación. Revisa primero los "
            "conceptos y el material recomendado, analiza el ejemplo paso a paso y sube tus ejercicios resueltos en "
            f"Moodle {plazo}.")


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
    temas = contenido["temas"][:MAX_TEMAS]
    generadas = indicaciones_estudiante(estudiante.get("nombres") or "", numero, contenido["titulo"],
                                        [t for t, _ in temas], fecha_entrega)
    materia = _materia(curso.get("fullname", ""), curso.get("shortname", ""))
    return {
        # En el PDF el estudiante ve el nombre de la materia, no el código interno del curso (SOF-ED-B)
        "titulo": titulo.replace(curso["shortname"], materia) if curso.get("shortname") else titulo,
        "estudiante": {"nombres": estudiante.get("nombres"), "cedula": estudiante.get("cedula"),
                       "email": estudiante.get("email"), "id_number": estudiante.get("id_number")},
        "materia": materia,
        "sigla": sigla_curso(curso.get("shortname", "")),
        "unidad": numero,
        "unidad_titulo": f"Unidad {numero}: {contenido['titulo']}",
        "docente": docente,
        "fecha_entrega": fecha_entrega,
        "instrucciones": (instrucciones or "").strip(),
        "indicaciones": _indicaciones(instrucciones, generadas),
        "diagnostico": _diagnostico(registro, numero, debiles) if registro else [],
        "temas": temas,
        "recursos": recursos_unidad(curso.get("shortname", ""), numero),
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
        self.cell(115, 4, _texto("GUÍA DE REFUERZO ACADÉMICO · UTA - FISEI"), align="R", new_x="LMARGIN", new_y="NEXT")
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
    pdf.ln(1.6)
    pdf.set_font("helvetica", "B", 10.5)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 5.6, _texto(texto), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*TEXTO)


def _parrafo(pdf: FPDF, texto: str, tam: float = 9.5, estilo: str = "", alto: float = 4.5) -> None:
    pdf.set_font("helvetica", estilo, tam)
    pdf.multi_cell(0, alto, _texto(texto), new_x="LMARGIN", new_y="NEXT")


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
    pdf.set_y(y + alto + 1.5)
    pdf.set_text_color(*TEXTO)


def _vinieta(pdf: FPDF, marca: str, texto: str) -> None:
    pdf.set_font("helvetica", "B", 9.5)
    pdf.cell(6, 4.5, _texto(marca))
    pdf.set_font("helvetica", "", 9.5)
    pdf.multi_cell(0, 4.5, _texto(texto), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(0.3)


def renderizar_pdf(guia: Dict[str, Any]) -> bytes:
    pdf = _GuiaPDF(format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(True, margin=15)
    pdf.set_title(_texto(f"Guía de refuerzo académico - {guia['titulo']}"))
    pdf.set_author("Universidad Técnica de Ambato · FISEI")
    pdf.set_creator("Universidad Técnica de Ambato · FISEI")
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
        pdf.ln(0.5)
        _tarjetas(pdf, guia["diagnostico"])

    _titulo_seccion(pdf, "Indicaciones del docente")
    _parrafo(pdf, guia["indicaciones"])

    _titulo_seccion(pdf, "Conceptos clave")
    for tema, explicacion in guia["temas"]:
        pdf.set_font("helvetica", "B", 9.5)
        pdf.write(4.5, _texto(f"{tema}: "))
        pdf.set_font("helvetica", "", 9.5)
        pdf.write(4.5, _texto(explicacion))
        pdf.ln(5.4)

    if guia.get("recursos"):
        _titulo_seccion(pdf, "Dónde consultar y reforzar")
        for fuente, detalle in guia["recursos"]:
            pdf.set_font("helvetica", "B", 9.5)
            pdf.cell(6, 4.5, "-")
            pdf.set_font("helvetica", "", 9.5)
            # Celda multilínea: las líneas siguientes quedan alineadas con el texto, no con el margen
            pdf.multi_cell(0, 4.5, _texto(f"**{fuente}:** {detalle}"), markdown=True, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(0.8)

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
