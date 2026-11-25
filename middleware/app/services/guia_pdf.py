"""
Guía de refuerzo académico en PDF con la diagramación sobria del «Formulario de guías prácticas de aplicación y
experimentación de los aprendizajes» de la Universidad Técnica de Ambato (FISEI), adaptada a una tarea individual.

Se genera al aprobar y publicar un refuerzo y se adjunta a la tarea de Moodle (plugin local_edumonitor).
Estilo: sólo negro sobre blanco, bordes negros finos y el escudo institucional; sin cuadros de color.
Estructura (1 a 2 páginas): cabecera institucional, tabla de datos generales y secciones
I. Tema · II. Objetivo · III. Modalidad y duración · IV. Instrucciones · V. Material y recursos ·
VI. Fundamentación y ejemplo resuelto · VII. Actividades por desarrollar.
Sin tablas bibliográficas, sin cuadro de validación ni rúbrica.
`construir_guia` arma el contenido sólo con datos reales y el catálogo de la materia; `renderizar_pdf` lo dibuja.
"""

import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from fpdf import FPDF

from app.services.contenidos_academicos import (contenido_unidad, entorno_materia, objetivo_unidad,
                                                 recursos_unidad, sigla_curso)

LOGO = Path(__file__).resolve().parent.parent / "recursos" / "uta-logo-azul.png"
ESCUDO_PX = (0, 0, 197, 210)   # el escudo dentro del logo (a la derecha está la marca nominativa)
NEGRO = (0, 0, 0)

UNIVERSIDAD = "UNIVERSIDAD TÉCNICA DE AMBATO"
SUBTITULO = "GUÍA DE REFUERZO ACADÉMICO Y APLICACIÓN DE APRENDIZAJES"
FACULTAD = "INGENIERÍA EN SISTEMAS, ELECTRÓNICA E INDUSTRIAL"
CARRERA = "Software"
NIVEL = "Cuarto"
CICLO = "Julio - Diciembre 2026"
MODALIDAD = "Virtual (Moodle UTA)"
DURACION = "2 horas no presenciales"
PIE = "UTA - FISEI"

NIVELES = {"CRITICO": "crítico", "EN_RIESGO": "en riesgo", "ACEPTABLE": "aceptable"}
MAX_TEMAS, MAX_PASOS, MAX_EJERCICIOS, MAX_ACTIVIDADES = 3, 5, 3, 3

# Medidas de la página (mm)
X0, ANCHO = 15.0, 180.0
CUERPO_Y = 36.0        # inicio del cuerpo bajo la cabecera de cada página
PAD = 2.0              # margen interior de las celdas y secciones
TAM, ALTO = 9.0, 4.3   # tipografía del cuerpo

# fpdf2 con fuentes estándar usa Latin-1: se sustituyen los pocos signos tipográficos que no lo admiten
_SUSTITUTOS = {"—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "′": "'", "″": '"', "…": "...",
               "•": "-", "≥": ">=", "≤": "<=", "→": "=>", "->": "=>", "←": "<=", "²": "^2", " ": " "}


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


def _lista(items: List[str]) -> str:
    """['a', 'b', 'c'] -> 'a, b y c'."""
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1] if items else ""


def _en_minuscula(subtemas: List[str]) -> List[str]:
    """Subtemas a mitad de frase en minúscula, salvo siglas («SQL avanzado», «HTML y CSS»)."""
    return [t if len(t) > 1 and t[1].isupper() else t[:1].lower() + t[1:] for t in subtemas]


def fecha_entrega_texto(fecha: Optional[datetime]) -> str:
    """datetime(2026, 12, 2, 23, 59) -> '02/12/2026 a las 23:59'."""
    if not fecha:
        return "La indicada en la tarea de Moodle UTA"
    return f"{fecha.strftime('%d/%m/%Y')} a las {fecha.strftime('%H:%M')}"


def _actividad(a: Dict[str, Any]) -> str:
    nombre = a.get("nombre") or a.get("id_number")
    if a.get("estado") == "SIN_ENTREGA":
        return f"{nombre} (sin entrega)"
    if a.get("estado") == "PENDIENTE" or a.get("nota") is None:
        return f"{nombre} (pendiente)"
    return f"{nombre} ({a['nota']:.2f})"


def motivo_refuerzo(registro: Dict[str, Any], numero: int, debiles: List[Dict[str, Any]]) -> Optional[str]:
    """Notas reales que motivan el refuerzo: nota de la unidad, actividades más bajas y nota ponderada."""
    if not registro:
        return None
    partes = []
    nota_unidad = (registro.get("promedios_unidad") or {}).get(f"U{numero}")
    if nota_unidad is not None:
        partes.append(f"tu promedio en la unidad es {nota_unidad:.2f}/10")
    if debiles:
        partes.append(f"las actividades con menor resultado fueron {_lista([_actividad(a) for a in debiles])}")
    if registro.get("nota_final") is not None:
        nivel = NIVELES.get(registro.get("nivel_riesgo"), "")
        partes.append(f"tu nota ponderada actual es {registro['nota_final']:.2f}/10" + (f" ({nivel})" if nivel else ""))
    return "; ".join(partes) if partes else None


def indicaciones_estudiante(nombres: str, numero: int, titulo_unidad: str, subtemas: List[str],
                            fecha_entrega: Optional[datetime] = None, motivo: Optional[str] = None) -> str:
    """Párrafo directo del docente: qué motiva el refuerzo, qué repasar y cómo y cuándo entregar en Moodle."""
    nombre = (nombres or "").split()[0] if nombres else "Estimado(a) estudiante"
    plazo = (f"hasta el {fecha_entrega_texto(fecha_entrega)}" if fecha_entrega
             else "hasta la fecha indicada en la tarea")
    return (f"{nombre}, este refuerzo corresponde a la Unidad {numero} ({titulo_unidad})"
            + (f": {motivo}" if motivo else "")
            + f". Repasa {_lista(_en_minuscula(subtemas))} con la fundamentación y el ejemplo de la sección VI, "
            "resuelve las actividades de la sección VII y sube un único archivo PDF (o tu código comprimido en .zip) "
            f"en la tarea de Moodle UTA {plazo}.")


# Textos que no escribió el docente: borradores en tercera persona («El estudiante X presenta dificultades...») o
# mensajes generados por esta u otras versiones de la guía. Se reemplazan por el párrafo actual con sus notas.
_TEXTO_GENERADO = re.compile(r"^\s*((el|la) (estudiante|alumn[oa])\b|estimado/a \S+, se ha identificado|"
                             r"hola \S+, revisando tus calificaciones|\S+, este refuerzo corresponde a la unidad)",
                             re.IGNORECASE)


def _indicaciones(instrucciones: str, generadas: str) -> str:
    """Instrucciones: el párrafo del docente con las notas de la unidad y, si las hay, sus observaciones."""
    texto = (instrucciones or "").strip()
    if not texto or _TEXTO_GENERADO.match(texto):
        return generadas
    if texto.lower().startswith(("estimado", "estimada", "hola")):
        return texto   # el docente ya le escribió directamente al estudiante
    return f"{generadas}\n**Observación del docente:** {texto}"


def construir_guia(*, estudiante: Dict[str, Any], curso: Dict[str, Any], unidad: Optional[str],
                   docente: str, titulo: str, instrucciones: str, fecha_entrega: Optional[datetime],
                   registro: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Contenido de la guía. `registro` es el registro analítico del estudiante en el curso (sincronización):
    notas por unidad, componentes y actividades; si falta, las instrucciones omiten las notas.
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
    motivo = motivo_refuerzo(registro, numero, debiles)
    generadas = indicaciones_estudiante(estudiante.get("nombres") or "", numero, contenido["titulo"], subtemas,
                                        fecha_entrega, motivo)
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
        "objetivo": f"{objetivo}.",
        "modalidad": MODALIDAD,
        "duracion": DURACION,
        "docente": docente,
        "fecha_entrega": fecha_entrega,
        "instrucciones": (instrucciones or "").strip(),
        "motivo": motivo,
        "indicaciones": _indicaciones(instrucciones, generadas),
        "temas": temas,
        "entorno": entorno_materia(shortname),
        "recursos": recursos_unidad(shortname, numero),
        "ejemplo": {**ejemplo, "pasos": ejemplo["pasos"][:MAX_PASOS]} if ejemplo else None,
        "ejercicios": contenido["ejercicios"][:MAX_EJERCICIOS],
    }


def datos_generales(guia: Dict[str, Any]) -> List[List[Tuple[str, str, int]]]:
    """Filas de la tabla de datos generales: celdas (etiqueta, valor, columnas que ocupa) sobre 3 columnas."""
    est = guia["estudiante"]
    contacto = " · ".join(v for v in (f"C.I. {est['cedula']}" if est.get("cedula") else "", est.get("email")) if v)
    return [
        [("FACULTAD", FACULTAD, 2), ("CARRERA", CARRERA, 1)],
        [("NIVEL", NIVEL, 1), ("CICLO ACADÉMICO", CICLO, 1), ("ASIGNATURA", guia["materia"].replace(" — ", " - "), 1)],
        [("DOCENTE", guia["docente"] or "-", 3)],
        [("ESTUDIANTE", (est.get("nombres") or "-") + (f" ({contacto})" if contacto else ""), 3)],
        [("FECHA LÍMITE DE ENTREGA", fecha_entrega_texto(guia.get("fecha_entrega")), 3)],
    ]


def nombre_archivo(guia: Dict[str, Any]) -> str:
    """'Guia_refuerzo_POO_U2_U-04.pdf' (sin espacios ni tildes: se usa como nombre del adjunto en Moodle)."""
    return f"Guia_refuerzo_{guia['sigla']}_U{guia['unidad']}_{guia['estudiante'].get('id_number') or 'estudiante'}.pdf"


@lru_cache(maxsize=1)
def _escudo():
    """Sólo el escudo de la UTA (sin la marca nominativa), como en el formulario oficial."""
    if not LOGO.exists():
        return None
    from PIL import Image
    return Image.open(LOGO).convert("RGBA").crop(ESCUDO_PX)


class _GuiaPDF(FPDF):
    def header(self):
        escudo = _escudo()
        if escudo is not None:
            self.image(escudo, x=X0, y=8, h=23)
        self.set_text_color(*NEGRO)
        self.set_xy(X0, 13)
        self.set_font("helvetica", "B", 12)
        self.cell(ANCHO, 5.5, _texto(UNIVERSIDAD), align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_x(X0)
        self.set_font("helvetica", "B", 10.5)
        self.cell(ANCHO, 5.5, _texto(SUBTITULO), align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_y(CUERPO_Y)

    def footer(self):
        self.set_y(-13)
        self.set_text_color(*NEGRO)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 6, _texto(f"Página {self.page_no()}/{{nb}} · {PIE}"), align="R")


def _escribir(pdf: FPDF, texto: str, tam: float = TAM, estilo: str = "", alto: float = ALTO) -> None:
    """Texto corrido con **negritas** y `código` (Courier, sin comillas); las líneas siguientes respetan la sangría."""
    for parte in re.split(r"(\*\*.+?\*\*|`[^`]+`)", texto):
        if not parte:
            continue
        if parte.startswith("**") and parte.endswith("**"):
            pdf.set_font("helvetica", "B", tam)
            parte = parte[2:-2]
        elif parte.startswith("`") and parte.endswith("`"):
            pdf.set_font("courier", "", tam)
            parte = parte[1:-1]
        else:
            pdf.set_font("helvetica", estilo, tam)
        pdf.write(alto, _texto(parte))
    pdf.ln(alto)


def _item(pdf: FPDF, marca: str, texto: str) -> None:
    """Elemento de lista simple con sangría francesa («- texto» o «1. texto»)."""
    izquierda = pdf.l_margin
    pdf.set_x(izquierda)
    pdf.set_font("helvetica", "", TAM)
    pdf.cell(5, ALTO, _texto(marca))
    pdf.set_left_margin(izquierda + 5)
    _escribir(pdf, texto)
    pdf.set_left_margin(izquierda)
    pdf.ln(0.4)


def _tabla_datos(pdf: FPDF, filas: List[List[Tuple[str, str, int]]]) -> None:
    """Tabla de datos generales con bordes negros finos: «ETIQUETA: valor» en cada celda."""
    columnas = (60.0, 55.0, 65.0)
    pdf.set_draw_color(*NEGRO)
    pdf.set_line_width(0.25)
    pdf.set_font("helvetica", "", 8.5)
    y = pdf.get_y()
    for fila in filas:
        celdas, x, i = [], X0, 0
        for etiqueta, valor, ocupa in fila:
            ancho = sum(columnas[i:i + ocupa])
            texto = _texto(f"**{etiqueta}:** {valor}")
            lineas = len(pdf.multi_cell(ancho - 2 * PAD, 4, texto, markdown=True, align="L", dry_run=True,
                                        output="LINES"))
            celdas.append((x, ancho, texto, lineas))
            x, i = x + ancho, i + ocupa
        alto = max(c[3] for c in celdas) * 4 + 2.4
        for x, ancho, texto, _ in celdas:
            pdf.rect(x, y, ancho, alto)
            pdf.set_xy(x + PAD, y + 1.2)
            pdf.multi_cell(ancho - 2 * PAD, 4, texto, markdown=True, align="L")
        y += alto
    pdf.set_y(y + 4)


def _seccion(pdf: FPDF, titulo: str, cuerpo: Callable[[], None]) -> None:
    """Sección del formulario: «I. TEMA:» en negrita y su contenido, enmarcados con bordes negros finos.
    Si la sección continúa en la página siguiente, el marco se dibuja en cada página."""
    if pdf.get_y() > 262:
        pdf.add_page()
    pagina0, y0 = pdf.page, pdf.get_y()
    pdf.set_left_margin(X0 + PAD)
    pdf.set_right_margin(pdf.w - X0 - ANCHO + PAD)
    pdf.set_xy(X0 + PAD, y0 + 1.2)
    pdf.set_text_color(*NEGRO)
    pdf.set_font("helvetica", "B", TAM)
    pdf.cell(0, ALTO + 0.4, _texto(titulo), new_x="LMARGIN", new_y="NEXT")
    cuerpo()
    pdf.ln(1.2)
    pdf.set_left_margin(X0)
    pdf.set_right_margin(pdf.w - X0 - ANCHO)
    pagina1, y1 = pdf.page, pdf.get_y()

    pdf.set_draw_color(*NEGRO)
    pdf.set_line_width(0.25)
    for pagina in range(pagina0, pagina1 + 1):
        pdf.page = pagina
        arriba = y0 if pagina == pagina0 else CUERPO_Y
        abajo = y1 if pagina == pagina1 else pdf.page_break_trigger
        pdf.line(X0, arriba, X0, abajo)
        pdf.line(X0 + ANCHO, arriba, X0 + ANCHO, abajo)
        if pagina == pagina0:
            pdf.line(X0, arriba, X0 + ANCHO, arriba)
        if pagina == pagina1:
            pdf.line(X0, abajo, X0 + ANCHO, abajo)
    pdf.page = pagina1
    pdf.set_y(y1)


def renderizar_pdf(guia: Dict[str, Any]) -> bytes:
    pdf = _GuiaPDF(format="A4")
    pdf.set_margins(X0, 15, X0)
    pdf.set_auto_page_break(True, margin=16)
    pdf.set_title(_texto(f"Guía de refuerzo académico - {guia['titulo']}"))
    pdf.set_author("Universidad Técnica de Ambato · FISEI")
    pdf.set_creator("Universidad Técnica de Ambato · FISEI")
    pdf.set_text_color(*NEGRO)
    pdf.set_draw_color(*NEGRO)
    pdf.alias_nb_pages()
    pdf.add_page()

    _tabla_datos(pdf, datos_generales(guia))

    _seccion(pdf, "I. TEMA:", lambda: _escribir(pdf, guia["unidad_titulo"]))
    _seccion(pdf, "II. OBJETIVO:", lambda: _escribir(pdf, guia["objetivo"]))
    _seccion(pdf, "III. MODALIDAD Y DURACIÓN:", lambda: _escribir(
        pdf, f"**Modalidad:** {guia['modalidad']} · **Duración:** {guia['duracion']}"))
    _seccion(pdf, "IV. INSTRUCCIONES:", lambda: _escribir(pdf, guia["indicaciones"]))

    def recursos():
        _item(pdf, "-", f"**Entorno de desarrollo:** {guia['entorno']}.")
        todos = guia.get("recursos") or []
        aula = [r for r in todos if r[0].startswith("Aula virtual")]
        for fuente, detalle in aula + [r for r in todos if r not in aula]:
            _item(pdf, "-", f"**{fuente}:** {detalle}")
    _seccion(pdf, "V. MATERIAL Y RECURSOS:", recursos)

    def fundamentacion():
        for tema, explicacion in guia["temas"]:
            _item(pdf, "-", f"**{tema}:** {explicacion}")
        ejemplo = guia.get("ejemplo")
        if ejemplo:
            pdf.ln(0.8)
            _escribir(pdf, f"**Ejemplo resuelto:** {ejemplo['enunciado']}")
            pdf.ln(0.4)
            for i, paso in enumerate(ejemplo["pasos"], 1):
                _item(pdf, f"{i}.", paso)
            _escribir(pdf, f"**Resultado:** {ejemplo['resultado']}")
    _seccion(pdf, "VI. FUNDAMENTACIÓN Y EJEMPLO RESUELTO:", fundamentacion)

    def actividades():
        _escribir(pdf, "Resuelve los siguientes ejercicios y sube tu desarrollo a la tarea de Moodle UTA:")
        pdf.ln(0.4)
        for i, ejercicio in enumerate(guia["ejercicios"], 1):
            _item(pdf, f"{i}.", ejercicio)
    _seccion(pdf, "VII. ACTIVIDADES POR DESARROLLAR:", actividades)

    return bytes(pdf.output())


def generar_guia_pdf(**datos: Any) -> Dict[str, Any]:
    """Atajo: construye la guía y devuelve {'guia', 'nombre', 'pdf'}."""
    guia = construir_guia(**datos)
    return {"guia": guia, "nombre": nombre_archivo(guia), "pdf": renderizar_pdf(guia)}
