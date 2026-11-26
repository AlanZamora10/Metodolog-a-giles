"""
CoraIA bilingüe (español / inglés) y delimitación del dominio académico.

- `detectar_idioma`: el docente puede escribir en español o en inglés; CoraIA responde en el mismo idioma.
- `traducir_consulta`: una consulta en inglés se lleva a las intenciones del planificador por reglas (que trabaja
  en español), así la respuesta usa exactamente las mismas herramientas y datos reales de MoodleUTADB.
- `cortesia_en`: saludos, agradecimientos y despedidas en inglés.
- `fuera_de_dominio`: cálculos generales, cultura general, chistes... se responden con el alcance de CoraIA.
- `secciones_en`: redacción en inglés de cada resultado de herramienta (los textos institucionales generados en
  español, como hallazgos del informe o la propuesta de refuerzo que se publica en Moodle, se conservan).
"""

import contextvars
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

IDIOMA: contextvars.ContextVar[str] = contextvars.ContextVar("idioma_coraia", default="es")

DOMINIO_ES = ("Soy CoraIA, asistente especializado únicamente en seguimiento académico, calificaciones y alertas "
              "tempranas de la UTA - FISEI. No respondo cálculos generales ni temas externos; puedo ayudarte con tus "
              "cursos, notas, estudiantes en riesgo o guías de refuerzo.")
DOMINIO_EN = ("I am CoraIA, an academic assistant specialized exclusively in student performance tracking, grades, and "
              "early alerts at UTA - FISEI. I do not answer general math or external topics; I can help you with your "
              "courses, grades, at-risk students, or study guides.")


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto.lower()).strip()


def t(es: str, en: str) -> str:
    """Texto en el idioma de la conversación actual."""
    return en if IDIOMA.get() == "en" else es


def resumen_incidencias(incidencias: List[str], textos: Dict[str, str], pendientes: Tuple[str, str]) -> str:
    """«U1-T2 (nota 0), U2-T4 (sin entrega) · 5 actividades pendientes de calificación».

    Las novedades reales (nota cero, sin entrega) se listan con su código; las pendientes de calificar se
    agrupan en un único conteo en lugar de repetir la misma frase por cada actividad.
    """
    reales, n_pendientes = [], 0
    for i in incidencias:
        codigo, _, tipo = i.partition(" ")
        if tipo == "PENDIENTE":
            n_pendientes += 1
        else:
            reales.append(f"{codigo} ({textos.get(tipo, tipo.lower())})")
    partes = [", ".join(reales)] if reales else []
    if n_pendientes:
        partes.append(plural(n_pendientes, *pendientes))
    return " · ".join(partes)


def incidencias_compactas(incidencias: List[str], textos: Dict[str, str], sin_calificar: str) -> str:
    """Celda de tabla: «U1-T2 nota 0, U2-T4 sin entrega · 5 sin calificar» (sin paréntesis ni frases largas)."""
    reales, pendientes = [], 0
    for i in incidencias:
        codigo, _, tipo = i.partition(" ")
        if tipo == "PENDIENTE":
            pendientes += 1
        else:
            reales.append(f"{codigo} {textos.get(tipo, tipo.lower())}")
    partes = [", ".join(reales)] if reales else []
    if pendientes:
        partes.append(f"{pendientes} {sin_calificar}")
    return " · ".join(partes) or "—"


def tabla_markdown(cabecera: List[str], filas: List[List[str]]) -> List[str]:
    """Tabla Markdown (GFM) lista para el chat; las barras verticales del contenido se escapan."""
    limpiar = lambda v: str(v).replace("|", "/")  # noqa: E731
    return (["| " + " | ".join(cabecera) + " |", "|" + "|".join(["---"] * len(cabecera)) + "|"]
            + ["| " + " | ".join(limpiar(v) for v in fila) + " |" for fila in filas])


def plural(n: int, singular: str, plural_: str) -> str:
    return f"{n} {singular if n == 1 else plural_}"


# ============================================================================ Detección de idioma
_PALABRAS_EN = {
    "hello", "hi", "hey", "good", "morning", "afternoon", "evening", "how", "are", "you", "doing", "many", "students",
    "student", "who", "has", "have", "the", "lowest", "highest", "worst", "best", "grade", "grades", "give", "what",
    "which", "my", "courses", "course", "list", "show", "please", "thanks", "thank", "bye", "goodbye", "am", "i", "do",
    "does", "at", "risk", "alerts", "alert", "summary", "support", "for", "of", "with", "name", "teach", "failing",
    "passing", "download", "generate", "full", "enrolled", "performance", "activities", "there", "can", "help",
    "overview", "report", "need", "attention", "struggling", "below", "above", "between", "than", "less", "greater",
    "prepare", "send", "guide", "scores", "score", "subjects", "classes", "whose", "about", "tell", "joke", "weather",
    "capital", "your", "doing", "fine", "great", "see", "later", "lot", "much", "welcome", "nice", "meet",
}
_PALABRAS_ES = {
    "que", "como", "cuantos", "cuantas", "cuanto", "de", "el", "la", "los", "las", "mis", "mi", "tengo", "dame", "hola",
    "quien", "quienes", "esta", "estan", "para", "por", "con", "en", "del", "y", "es", "son", "un", "una", "notas",
    "nota", "estudiantes", "alumnos", "cursos", "curso", "lista", "peor", "mejor", "buenos", "buenas", "gracias",
    "dias", "tardes", "noches", "sobre", "materia", "materias", "apoyo", "resumen", "prepara", "preparame", "dime",
    "muestrame", "tiene", "va", "van", "estas", "chao", "adios", "perfecto", "genial", "descargar", "genera", "eres",
}


def detectar_idioma(mensaje: str) -> str:
    """'en' si el mensaje está escrito en inglés; 'es' en cualquier otro caso (idioma por defecto)."""
    palabras = re.findall(r"[a-z]+", _norm(mensaje))
    en = sum(1 for p in palabras if p in _PALABRAS_EN)
    es = sum(1 for p in palabras if p in _PALABRAS_ES)
    return "en" if en > es else "es"


# ============================================================================ Consulta en inglés -> intención
_TRADUCCIONES: List[Tuple[str, str]] = [
    # Guía en PDF
    (r"\b(give|send|get) me (the |a )?(pdf|guide)\b|\bdownload (the |a )?(pdf|guide)\b|\bgenerate (the |a )?(pdf|guide)\b",
     "dame el pdf"),
    (r"\b(pdf|guide) (of|for)\b", "pdf de"),
    # Materias por su nombre en inglés
    (r"\bobject[- ]oriented programming\b|\boop\b", "poo"),
    (r"\bdata structures?\b", "ed"),
    (r"\bagile (software )?(development )?methodolog(y|ies)\b|\bagile\b", "ma"),
    (r"\bsoftware configuration( management)?\b", "mcs"),
    (r"\bsoftware engineering( i| 1)?\b", "is1"),
    (r"\badvanced databases?\b", "bda"),
    (r"\bweb development\b", "dw"),
    # Conteo, nómina y extremos
    (r"\bhow many (students|pupils|learners|people)\b", "cuantos estudiantes"),
    (r"\bhow many courses\b", "cuantos cursos"),
    (r"\b(who has|who got|which student has|student with|who is the student with) the (lowest|worst) "
     r"(grade|score|mark|average)\b", "quien tiene la peor nota"),
    (r"\b(who has|who got|which student has|student with|who is the student with) the (highest|best) "
     r"(grade|score|mark|average)\b", "quien tiene la mejor nota"),
    (r"\bthe (lowest|worst) (grade|score|mark)\b", "la peor nota"),
    (r"\bthe (highest|best) (grade|score|mark)\b", "la mejor nota"),
    (r"\b(the )?(best|top) student\b", "el mejor estudiante"),
    (r"\b(the )?(worst|weakest) student\b", "el peor estudiante"),
    (r"\b(full |complete )?(list|roster) of (the )?students\b|\b(full|complete) (list|roster)\b|\bstudent list\b|"
     r"\bclass list\b|\broster\b", "lista completa de"),
    (r"\bwho (is|are) (enrolled )?(in|on)\b", "quienes estan en"),
    (r"\blist\b", "lista"),
    # Perfil del docente
    (r"\b(what is my name|whats my name|who am i|my profile|my details)\b", "quien soy"),
    (r"\bwhat (subjects|courses|classes) do i teach\b", "que materias doy"),
    (r"\b(all (of )?my courses|in total)\b", "todos mis cursos"),
    (r"\b(my courses|my subjects|my classes|what courses do i have|which courses do i have)\b", "mis cursos"),
    # Seguimiento
    (r"\b(support|reinforcement|remedial|improvement|study|recovery) plan\b", "plan de apoyo"),
    (r"\bhow (are|is) (all )?my courses (doing|going)\b", "como van mis cursos"),
    (r"\bhow is ([a-z ]+?) doing\b", r"como va \1"),
    (r"\b(lowest|worst) (performing )?activities\b|\bactivities with (the )?(lowest|worst) (performance|average)\b",
     "actividades con menor rendimiento"),
    (r"\b(at risk|at-risk|struggling|in trouble|need(s)? (help|attention))\b", "en riesgo"),
    (r"\bwho is failing\b|\bfailing( students)?\b", "reprobados"),
    (r"\bpassing( students)?\b", "aprobados"),
    (r"\b(summary|overview|report)\b", "resumen"),
    (r"\b(grades|scores|marks)\b", "notas"),
    (r"\b(grade|score|mark|average)\b", "nota"),
    (r"\balerts?\b", "alertas"),
    (r"\bstudents\b", "estudiantes"),
    (r"\bstudent\b", "estudiante"),
    (r"\b(less than|lower than|below|under)\b", "menor a"),
    (r"\b(greater than|higher than|more than|above|over)\b", "mayor a"),
    (r"\bbetween\b", "entre"),
    (r"\band\b", "y"),
    (r"\b(in|on|at)\b", "en"),
    (r"\bfor\b", "para"),
    (r"\b(of|from)\b", "de"),
]
_RELLENO_EN = {"please", "do", "does", "i", "have", "the", "a", "an", "me", "can", "you", "could", "would", "show",
               "tell", "what", "which", "my", "get", "give", "prepare", "make", "create", "now", "perfect", "great",
               "ok", "okay", "so", "then", "there", "are", "who", "how", "with", "to", "it", "that", "this", "thanks",
               "thank", "hey", "hi", "hello", "about"}


def traducir_consulta(mensaje: str) -> str:
    """Consulta en inglés -> frase equivalente en español para el planificador (nombres y siglas se conservan)."""
    texto = _norm(mensaje)
    for patron, reemplazo in _TRADUCCIONES:
        texto = re.sub(patron, reemplazo, texto)
    palabras = [p for p in re.findall(r"[a-z0-9.,<>=+-]+", texto) if p not in _RELLENO_EN]
    return " ".join(palabras)


# ============================================================================ Cortesía en inglés
_CORTESIA_EN = {
    "hello", "hi", "hey", "good", "morning", "afternoon", "evening", "how", "are", "you", "doing", "thanks", "thank",
    "bye", "goodbye", "see", "later", "ok", "okay", "great", "perfect", "cool", "there", "coraia", "a", "lot", "very",
    "much", "fine", "nice", "to", "meet", "today", "is", "it", "going", "what", "can", "do", "help", "me", "who",
    "your", "and", "so", "awesome", "excellent", "got",
}


def _ejemplos_en() -> str:
    return "\n".join(f"- «{e}»" for e in ("How many students do I have in POO?", "Who has the lowest grade in ED?",
                                          "Prepare a support plan for Carlos Mendoza", "Give me the PDF"))


def cortesia_en(mensaje: str, docente: dict) -> Optional[str]:
    """Respuesta inmediata a saludos y cortesías en inglés; None si el mensaje trae una consulta real."""
    if re.search(r"\d", mensaje or ""):
        return None   # con cifras ya no es una cortesía
    texto = " ".join(re.findall(r"[a-z]+", _norm(mensaje)))
    palabras = texto.split()
    if not palabras or len(palabras) > 8 or any(p not in _CORTESIA_EN for p in palabras):
        return None
    nombre = (docente.get("nombres") or "").split()[0] if docente.get("nombres") else "Professor"
    if re.search(r"\b(what can you do|help me|who are you|help)\b", texto):
        return ("I'm CoraIA, the academic assistant of UTA - FISEI. I review your Moodle UTA courses, detect at-risk "
                f"students and prepare support plans and study guides. You can ask me, for example:\n{_ejemplos_en()}")
    if re.search(r"\bhow are you\b|\bhow is it going\b|\bhow are you doing\b", texto):
        return (f"I'm doing well, thank you, {nombre}! Ready to help you review your courses or prepare a support "
                "plan. What would you like to check today?")
    if re.search(r"\b(bye|goodbye|see you)\b", texto):
        return f"Goodbye, {nombre}! Have a great day."
    if re.search(r"\bthank", texto):
        return f"You're welcome, {nombre}! Let me know if you need anything else."
    momento = re.search(r"\bgood (morning|afternoon|evening)\b", texto)
    if momento:
        return f"Good {momento.group(1)}, {nombre}! How can I help you with your courses today?"
    if re.search(r"\b(ok|okay|great|perfect|cool|awesome|excellent|got it)\b", texto):
        return "Great. Whenever you want, I can review alerts, a student's grades or prepare a support plan."
    return (f"Hello, {nombre}! I'm CoraIA, the academic assistant of UTA - FISEI. I can review your courses, detect "
            f"at-risk students and prepare support plans. For example:\n{_ejemplos_en()}")


# ============================================================================ Dominio académico
_ACADEMICO = re.compile(
    r"\b(curso|cursos|materia|materias|nota|notas|calificacion\w*|estudiante\w*|alumn\w*|alerta\w*|riesgo|refuerzo|"
    r"guia|pdf|promedio|parcial|unidad|tarea\w*|deber\w*|actividad\w*|examen\w*|evaluacion\w*|plan|reporte|informe|"
    r"resumen|matricul\w*|docente|paralelo|poo|ed|ma|mcs|is1|bda|dw|moodle|sincroniz\w*|apoyo|student\w*|grade\w*|"
    r"course\w*|alert\w*|risk|guide|assignment\w*|unit|class\w*|teacher|support|revisar|revisemos|consultar|"
    r"seguimiento|review|check)\b")
_CALCULO = re.compile(r"\d\s*[-+*/x^%]\s*\d|\b(raiz cuadrada|square root|derivada|integral de|factorial)\b")
_SOLO_CALCULO = re.compile(r"^(cuanto (es|da|son)|what is|whats|calcula|calculate|solve|resuelve|how much is)?"
                           r"[\s\d+\-*/x^%().,=?]+$")
_CULTURA_GENERAL = re.compile(
    r"\b(capital (de|of)|presidente|president|chiste|joke|clima|weather|temperatura|receta|recipe|futbol|football|"
    r"soccer|pelicula|movie|cancion|song|poema|poem|horoscopo|noticias|news|bitcoin|precio del|price of|quien gano|"
    r"who won|traduce|translate|historia de|history of|cuentame un|tell me a|mundial|world cup|raiz cuadrada|"
    r"square root|planeta|planet|que hora es|what time is it)\b")


def es_academico(texto_normalizado: str) -> bool:
    return bool(_ACADEMICO.search(texto_normalizado))


def fuera_de_dominio(mensaje: str) -> bool:
    """Cálculos generales («2 + 2») o temas externos (capitales, chistes, clima...) sin relación académica."""
    texto = _norm(mensaje)
    if _SOLO_CALCULO.match(texto) and _CALCULO.search(texto):
        return True
    if _CALCULO.search(texto) and not es_academico(texto):
        return True
    return bool(_CULTURA_GENERAL.search(texto)) and not es_academico(texto)


def mensaje_dominio() -> str:
    return t(DOMINIO_ES, DOMINIO_EN)


# ============================================================================ Redacción en inglés
NIVEL_EN = {"CRITICO": "critical", "EN_RIESGO": "at risk", "ACEPTABLE": "acceptable"}
ESTADO_ALERTA_EN = {"ABIERTA": "open", "ATENDIDA": "in progress", "PUBLICADO": "reinforcement published"}
TENDENCIA_EN = {"SUBE": "upward", "BAJA": "downward", "ESTABLE": "stable"}
INCIDENCIA_EN = {"SIN_ENTREGA": "not submitted", "PENDIENTE": "pending grading", "NOTA_0": "grade 0"}
COMPONENTE_EN = {"acd": "Exams", "tareas": "Assignments", "pae": "APE"}
OPERADORES_EN = {"<": "below", "<=": "at most", ">": "above", ">=": "at least"}

Seccion = Tuple[str, str, List[str]]


def curso_en(fullname: str) -> str:
    """'Programación orientada a objetos — Section A' (la materia conserva su nombre oficial)."""
    from app.services.agente_herramientas import _nombre_curso
    return _nombre_curso(fullname).replace(", paralelo", " — Section")


def _nivel(f: Dict[str, Any]) -> str:
    return NIVEL_EN.get(f.get("nivel_riesgo"), (f.get("nivel_riesgo") or "").lower())


def _f(v: Optional[float]) -> str:
    return "—" if v is None else f"{v:.2f}"


def _y(items: List[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def criterio_en(c: Dict[str, Any]) -> str:
    if c["operador"] == "entre":
        return f"grade between {c['umbral']:.2f} and {c['umbral_max']:.2f}"
    return f"grade {OPERADORES_EN[c['operador']]} {c['umbral']:.2f}"


def _alcance(r: Dict[str, Any]) -> str:
    cursos = r.get("cursos_consultados") or []
    return f"in **{curso_en(cursos[0]['fullname'])}**" if len(cursos) == 1 else f"in your {len(cursos)} courses"


def _cursos(r):
    if not r["cursos"]:
        return ("Assigned courses", "You have no synchronized courses.",
                ["Press **Sincronizar** to import your courses from Moodle UTA."])
    tt = r["totales"]
    clave = (f"You have **{plural(tt['cursos'], 'course', 'courses')}** with "
             f"**{plural(tt['estudiantes_unicos'], 'unique student', 'unique students')}** "
             f"({plural(tt['matriculas'], 'enrollment', 'enrollments')} in total).")
    return "Assigned courses", clave, [f"- **{curso_en(c['fullname'])}**: {plural(c['total_estudiantes'], 'student', 'students')}"
                                       for c in r["cursos"]]


def _extremo(r):
    filas, peor = r["calificaciones"], r["extremo"] == "peor"
    cursos = r.get("cursos_consultados") or []
    una = len(cursos) == 1
    alcance = f"In **{curso_en(cursos[0]['fullname'])}**" if una else f"Across your {len(cursos)} courses"
    if not filas:
        return "Grades", f"{alcance} there are no synchronized grades yet.", []
    adj = "lowest" if peor else "highest"
    donde = (lambda f: "") if una else (lambda f: f" in {curso_en(f['curso_nombre'])}")
    primero = filas[0]
    empatados = [f for f in filas if f["nota_final"] == primero["nota_final"]]
    if len(empatados) == 1:
        clave = (f"{alcance}, the student with the **{adj} grade** is **{primero['nombres']}**{donde(primero)}, "
                 f"with **{primero['nota_final']:.2f}/10** ({_nivel(primero)}).")
    else:
        clave = (f"{alcance}, **{len(empatados)} students** share the {adj} grade (**{primero['nota_final']:.2f}/10**, "
                 f"{_nivel(primero)}): " + _y([f"**{f['nombres']}**{donde(f)}" for f in empatados]) + ".")
    restantes = filas[len(empatados):]
    otros = [f for f in restantes if f["nivel_riesgo"] != "ACEPTABLE"][:5] if peor else restantes[:2]
    lineas = ([("Also need follow-up:" if peor else "Next:")]
              + [f"- {f['nombres']}{donde(f)}: **{f['nota_final']:.2f}/10** ({_nivel(f)})" for f in otros]) if otros else []
    return ("Lowest grade" if peor else "Highest grade"), clave, lineas


def _calificaciones(r):
    filas = r["calificaciones"]
    if r.get("extremo"):
        return _extremo(r)
    if r.get("criterio"):
        criterio = criterio_en(r["criterio"])
        if not filas:
            return "Grades", f"No enrollment has **{criterio}** {_alcance(r)}.", []
        una = len(r.get("cursos_consultados") or []) == 1
        return (f"Grades with {criterio}",
                f"I found **{plural(len(filas), 'enrollment', 'enrollments')}** with **{criterio}** {_alcance(r)}:",
                [f"- **{f['nombres']}**" + ("" if una else f" · {curso_en(f['curso_nombre'])}")
                 + f": **{f['nota_final']:.2f}/10** ({_nivel(f)})" for f in filas])
    if r.get("estudiante"):
        nombre = filas[0]["nombres"]
        cedula = f" (ID {filas[0]['cedula']})" if filas[0].get("cedula") else ""
        n = len(filas)
        if n == 1:
            f0 = filas[0]
            clave = (f"**{nombre}**{cedula} · Has **{f0['nota_final']:.2f}/10** ({_nivel(f0)}) in "
                     f"**{curso_en(f0['curso_nombre'])}**.")
        else:
            criticos = sum(1 for f in filas if f["nivel_riesgo"] == "CRITICO")
            promedio = sum(f["nota_final"] for f in filas) / n
            estado = (f"**critical in all {n} courses**" if criticos == n
                      else "no course at critical level" if criticos == 0
                      else f"**critical in {criticos} of {n} courses**")
            clave = (f"**{nombre}**{cedula} · Enrolled in **{n} courses** with an overall average of "
                     f"**{promedio:.2f}/10** ({estado}).")
        # Indicadores por asignatura en una tabla compacta (sin listas repetitivas)
        lineas = tabla_markdown(
            ["Course", "Exams", "Assignments", "APE", "Average", "Level", "Trend", "Issues"],
            [[curso_en(f["curso_nombre"]), _f(f["acd"]), _f(f["tareas"]), _f(f["pae"]), f"**{f['nota_final']:.2f}**",
              _nivel(f).capitalize(), TENDENCIA_EN.get(f["tendencia"], (f["tendencia"] or "—").lower()).capitalize(),
              incidencias_compactas(f["incidencias"], {"SIN_ENTREGA": "not submitted", "NOTA_0": "grade 0"},
                                    "pending grading")]
             for f in sorted(filas, key=lambda x: x["nota_final"])])
        return f"Grades of {nombre}", clave, lineas
    por_curso: Dict[str, List[Dict[str, Any]]] = {}
    for f in filas:
        por_curso.setdefault(f["curso"], []).append(f)
    criticos = sum(1 for f in filas if f["nivel_riesgo"] == "CRITICO")
    en_riesgo = sum(1 for f in filas if f["nivel_riesgo"] == "EN_RIESGO")
    incid = lambda f: f" · {plural(len(f['incidencias']), 'issue', 'issues')}" if f["incidencias"] else ""  # noqa: E731
    if len(por_curso) == 1:
        aprobados = sum(1 for f in filas if f["nota_final"] >= 7)
        clave = (f"In **{curso_en(filas[0]['curso_nombre'])}** I reviewed **{plural(len(filas), 'grade', 'grades')}** "
                 f"({aprobados} passing): **{criticos} at critical level** and {en_riesgo} at risk.")
        seguimiento = sorted((f for f in filas if f["nivel_riesgo"] != "ACEPTABLE"), key=lambda x: x["nota_final"])
        return "Grades", clave, [f"- {f['nombres']}: **{f['nota_final']:.2f}/10** ({_nivel(f)}){incid(f)}"
                                 for f in seguimiento[:6]] or ["- All students are passing."]
    clave = (f"I reviewed **{plural(len(filas), 'grade', 'grades')}** in {len(por_curso)} courses: **{criticos} at "
             f"critical level** and {en_riesgo} at risk.")
    lineas = []
    for curso, lista in por_curso.items():
        lista.sort(key=lambda x: x["nota_final"])
        aprobados = sum(1 for f in lista if f["nota_final"] >= 7)
        lineas.append(f"- **{curso}** ({plural(len(lista), 'student', 'students')}, {aprobados} passing)")
        seguimiento = [f for f in lista if f["nivel_riesgo"] != "ACEPTABLE"]
        lineas += [f"  - {f['nombres']}: **{f['nota_final']:.2f}/10** ({_nivel(f)}){incid(f)}" for f in seguimiento[:6]]
        if not seguimiento:
            lineas.append("  - All students are passing.")
    return "Grades", clave, lineas


def _alertas(r):
    alertas = sorted(r["alertas"], key=lambda a: (a.get("nota_final") is None, a.get("nota_final") or 0))
    if not alertas:
        return "Early alerts", "There are no active alerts for this query.", []
    abiertas = sum(1 for a in alertas if a["estado"] == "ABIERTA")
    clave = (f"There {'is' if len(alertas) == 1 else 'are'} **{plural(len(alertas), 'active alert', 'active alerts')}**; "
             f"{abiertas} {'is' if abiertas == 1 else 'are'} still open and "
             f"{'requires' if abiertas == 1 else 'require'} priority attention.")
    lineas = [f"- **{a['nombres']}** ({a['curso']}) · "
              f"{'Critical grade' if a['regla'].startswith('R1') else 'Sustained decline'} · grade **{_f(a.get('nota_final'))}/10**"
              + (f" · slope {a['pendiente']:+.2f}" if a.get("pendiente") is not None else "")
              + f" · {ESTADO_ALERTA_EN.get(a['estado'], a['estado'].lower())}" for a in alertas]
    if abiertas:
        lineas.append("\n**Tip:** handle the open alerts first from the *Centro de alertas* or ask me to prepare a "
                      "support plan for a specific student.")
    return "Early alerts", clave, lineas


def _resumen(r):
    secciones = []
    for s in r["resumenes"]:
        m, d = s["metricas"], s["distribucion_estados"]
        clave = (f"**{s['curso']}** has an average of **{m['promedio']:.2f}/10** and **{m['porcentaje_aceptables']:.1f} %** "
                 "passing.")
        lineas = [
            f"- **Average:** {m['promedio']:.2f}/10 (median {m['mediana']:.2f}; range {m['nota_minima']:.2f}–{m['nota_maxima']:.2f})",
            f"- **Levels:** {m['criticos']} critical, {m['en_riesgo']} at risk and {m['aceptables']} acceptable out of "
            f"{m['total_estudiantes']}",
            f"- **Submissions:** {d['cero']} with grade 0, {d['sin_entrega']} not submitted and {d['pendiente']} pending "
            f"out of {plural(d['total_registros'], 'record', 'records')}",
        ]
        if s["hallazgos"][1:]:
            lineas += ["\n**Key findings** (from the course report)"] + [f"- {h}" for h in s["hallazgos"][1:4]]
        if s["recomendaciones"]:
            lineas += ["\n**Recommendations** (from the course report)"] + [f"- {x}" for x in s["recomendaciones"][:3]]
        secciones.append((f"Summary of {s['curso']}", clave, lineas))
    return secciones or [("Summary", "There are no courses to summarize.", [])]


def _actividades(r):
    acts = [a for a in r["actividades"] if a["promedio"] is not None]
    if not acts:
        return "Performance by activity", "There are no graded activities in this scope.", []
    peor = acts[0]
    clave = (f"The activity with the lowest performance is **{peor['actividad']} · {peor['nombre']}** in {peor['curso']} "
             f"(average **{peor['promedio']:.2f}/10**).")
    lineas = ["Activities with the lowest average (lowest first):"]
    for a in acts[:5]:
        extras = [f"{a['bajo_aprobacion']} of {a['calificaciones']} below 7.00"]
        if a["ceros"]:
            extras.append(f"{a['ceros']} with grade 0")
        if a["sin_entrega"]:
            extras.append(f"{a['sin_entrega']} not submitted")
        if a["pendientes"]:
            extras.append(f"{a['pendientes']} pending")
        lineas.append(f"- **{a['curso']} · {a['actividad']}** {a['nombre']}: **{a['promedio']:.2f}/10** · " + ", ".join(extras))
    lineas.append("\n**Tip:** review the instructions and feedback of these activities and consider a group "
                  "reinforcement session on those topics.")
    return "Performance by activity", clave, lineas


def _refuerzo(r):
    p, ev, est = r["propuesta"], r["evidencia"], r["estudiante"]
    clave = (f"I prepared a support plan for **{est['nombres']}** in **{r['curso']}**, where the current grade is "
             f"**{ev['nota_final']:.2f}/10**.")
    lineas = ["**Detected weaknesses**"]
    if ev["unidad_critica"]:
        lineas.append(f"- Lowest unit: **Unit {ev['unidad_critica'][1:]}** ({_f(ev['promedio_unidad_critica'])}/10)")
    if ev["componente_debil"]:
        peso = {"acd": 40, "tareas": 30, "pae": 30}[ev["componente_debil"]]
        lineas.append(f"- Weakest component: **{COMPONENTE_EN[ev['componente_debil']]}** (weight {peso} %): "
                      f"{_f(ev['promedio_componente_debil'])}/10")
    if ev["incidencias"]:
        lineas.append("- Issues: " + ", ".join(f"{i['actividad']} ({INCIDENCIA_EN[i['tipo']]})" for i in ev["incidencias"]))
    lineas += ["", "*The plan is written in Spanish because it is published to the student in Moodle UTA.*", "",
               f"**Title:** {p['titulo']}", "", f"**Objective:** {p['objetivo']}", "", "**Task description**"]
    lineas += [f"{i}. {paso}" for i, paso in enumerate(p["pasos"], 1)]
    lineas += ["", f"**Suggested deadline:** {p['plazo_dias']} days."]
    if r["otros_cursos"]:
        lineas.append("\nOther courses of the student: " + ", ".join(
            f"{o['curso']} ({o['nota_final']:.2f}/10)" for o in r["otros_cursos"]) + ".")
    if r["alerta"] and r["alerta"]["estado"] in ("ABIERTA", "ATENDIDA"):
        lineas.append(f"\nYou can apply it from the **Centro de alertas** (alert #{r['alerta']['id']}) to review it and "
                      "publish it in Moodle.")
    elif r["alerta"]:
        lineas.append("\nThe student already has a published reinforcement for this alert in Moodle.")
    else:
        lineas.append("\nThe student has no active alert in this course; the plan is kept as a reference.")
    lineas.append("\nIf you want the **official PDF guide** for the student, type «give me the pdf».")
    return "Support plan", clave, lineas


def _nomina(r):
    curso = curso_en(r["curso"]["fullname"])
    if r["solo_conteo"]:
        return "Students", f"In **{curso}** you have **{plural(r['total'], 'student', 'students')}** enrolled.", []
    lineas = [f"{i}. **{e['nombres']}** · {e.get('email') or 'no email'} · current grade **{e['nota_final']:.2f}/10** "
              f"({_nivel(e)})" for i, e in enumerate(r["estudiantes"], 1)]
    return f"Students of {curso}", f"Students enrolled in **{curso}** ({r['total']}):", lineas


def _perfil(r):
    cedula = f", ID {r['cedula']}" if r.get("cedula") else ""
    n = len(r["cursos"])
    clave = (f"You are **{r['nombres']}** ({r['email']}{cedula}), a FISEI professor. You have "
             f"**{plural(n, 'assigned course', 'assigned courses')}** in the July–December 2026 term:")
    return "Your profile", clave, [f"- **{curso_en(c['fullname'])}**: {plural(c['total_estudiantes'], 'student', 'students')}"
                                   for c in r["cursos"]]


def _guia(r):
    est = r["estudiante"]
    unidad = re.sub(r"^Unidad (\d)", r"Unit \1", r["unidad"])
    clave = (f"Done: I generated the **official UTA - FISEI reinforcement guide** for **{est['nombres']}** in "
             f"**{curso_en(r['curso_nombre'])}** ({unidad}).")
    return "Reinforcement guide (PDF)", clave, [
        "Open or download it with the **Download PDF guide** button in this message. It includes the topic, the "
        "objective, the instructions, the study material, a solved example and the activities to complete "
        "(the guide itself is in Spanish, as it is delivered to the student)."]


_SECCIONES_EN = {
    "listar_cursos_autorizados": lambda r: [_cursos(r)],
    "obtener_calificaciones": lambda r: [_calificaciones(r)],
    "identificar_alertas": lambda r: [_alertas(r)],
    "generar_resumen": _resumen,
    "analizar_actividades": lambda r: [_actividades(r)],
    "proponer_refuerzo": lambda r: [_refuerzo(r)],
    "listar_estudiantes": lambda r: [_nomina(r)],
    "perfil_docente": lambda r: [_perfil(r)],
    "generar_guia_pdf": lambda r: [_guia(r)],
}


def secciones_en(nombre: str, r: Dict[str, Any]) -> List[Seccion]:
    if "error" in r:
        return [("Notice", f"I couldn't complete one of the queries: {r['error']}", [])]
    return _SECCIONES_EN.get(nombre, lambda _: [])(r)
