"""
NLU flexible de CoraIA: lleva el lenguaje natural del docente a una forma canónica que entienden las reglas.

- Sinónimos: «alumno/alumnos/chicos» = estudiante(s); «jalando / reprobaron / no pasan» = reprobados;
  «aprobaron / pasaron» = aprobados.
- Frases coloquiales de rendimiento: «el alumno más bajo de promedio», «quién va ganando la materia»,
  «menor promedio», «promedio más alto» -> «el estudiante con la peor / mejor nota».
- Intenciones nuevas: ranking de notas («dame el ranking», «ordenados de mayor a menor») y actividades
  pendientes de calificar («¿qué tareas faltan por calificar?»).
- Coincidencia parcial de materias: raíces sin plural («base de datos» -> Bases de Datos Avanzadas) y una palabra
  distintiva larga basta si sólo aparece en un curso («programación» -> Programación orientada a objetos).

Todo opera sobre texto normalizado (minúsculas, sin tildes) y no consulta datos: es determinista y rápido.
"""

import re
from typing import Any, Dict, List, Optional

# Orden importante: primero las frases completas, después las palabras sueltas.
_REEMPLAZOS = [
    # «¿quién va ganando la materia?», «quién va primero» -> el mejor; «quién va último» -> el peor
    (r"\bquien(?:es)? (?:va|van|esta|estan|iria|sigue|siguen) (?:ganando|primero|a la cabeza|en primer lugar|"
     r"liderando)(?: (?:la|el|en la|en el) (?:materia|curso|clase|asignatura))?\b", "el estudiante con la mejor nota"),
    (r"\bquien(?:es)? (?:va|van|esta|estan|sigue|siguen) (?:ultimo|en ultimo lugar|al final|a la cola)"
     r"(?: (?:la|el|en la|en el) (?:materia|curso|clase|asignatura))?\b", "el estudiante con la peor nota"),
    # «el alumno más bajo de promedio», «el estudiante con menor nota», «la alumna más floja»
    (r"\b(?:el |la )?(?:estudiante|alumn[oa]) (?:con |que tiene |que va )?(?:el |la )?(?:mas bajo|mas baja|menor|peor|"
     r"mas flojo|mas floja|mas atrasado|mas atrasada)(?: de| en)?(?: (?:promedio|nota|calificacion|rendimiento))?\b",
     "el estudiante con la peor nota"),
    (r"\b(?:el |la )?(?:estudiante|alumn[oa]) (?:con |que tiene |que va )?(?:el |la )?(?:mas alto|mas alta|mayor|mejor|"
     r"destacad[oa]|mas destacad[oa]|sobresaliente)(?: de| en)?(?: (?:promedio|nota|calificacion|rendimiento))?\b",
     "el estudiante con la mejor nota"),
    (r"\b(?:el |la )?(?:peor|menor) (?:alumn[oa]|estudiante)\b", "el estudiante con la peor nota"),
    (r"\b(?:el |la )?(?:mejor|mayor) (?:alumn[oa]|estudiante)\b", "el estudiante con la mejor nota"),
    # «menor promedio», «promedio más bajo», «más bajo de promedio» -> «la peor nota» (y su contrario)
    (r"\b(?:el |la )?(?:menor|peor) promedio\b|\b(?:el |la )?promedio mas bajo\b|\bmas bajo de promedio\b|"
     r"\b(?:la )?nota mas baja\b", "la peor nota"),
    (r"\b(?:el |la )?(?:mayor|mejor) promedio\b|\b(?:el |la )?promedio mas alto\b|\bmas alto de promedio\b|"
     r"\b(?:la )?nota mas alta\b", "la mejor nota"),
    # reprobados / aprobados coloquiales (los negativos antes que «pasan»)
    (r"\b(?:jalando|jalaron|jalan|se jalan|van jalando|reprobando|reprobaron|reprueban|perdiendo la materia|"
     r"pierden la materia|perdieron la materia|se quedan|quedandose|no pasan|no pasaron|no aprobaron)\b", "reprobados"),
    (r"\b(?:aprobaron|aprobaran|pasaron|pasan la materia|van pasando|estan pasando|ganaron la materia|"
     r"ganan la materia)\b", "aprobados"),
    # alumnos / chicos -> estudiantes
    (r"\b(?:alumn[oa]s|chic[oa]s|muchach[oa]s|estudiantado|pupilos)\b", "estudiantes"),
    (r"\balumn[oa]\b", "estudiante"),
    # abreviaturas y nombres coloquiales de las materias
    (r"\bbase de datos\b|\bbases de datos\b|\bbdd\b", "bda"),
    (r"\bprogramacion oo\b|\borientada a objetos\b", "poo"),
    (r"\bestructuras? de datos\b", "ed"),
    (r"\bmetodologias? agiles?\b|\bagiles\b", "ma"),
    (r"\bdesarrollo web\b", "dw"),
    (r"\bingenieria de software( i| 1)?\b|\bsoftware i\b|\bsoftware 1\b", "is1"),
    (r"\bmanejo y configuracion( del software)?\b|\bconfiguracion del software\b", "mcs"),
]
_COMPILADOS = [(re.compile(p), r) for p, r in _REEMPLAZOS]


def canonizar(texto: str) -> str:
    """Texto normalizado -> forma canónica (sinónimos, coloquialismos y abreviaturas de materias)."""
    for patron, reemplazo in _COMPILADOS:
        texto = patron.sub(reemplazo, texto)
    return re.sub(r"\s+", " ", texto).strip()


# Ranking de notas: «dame el ranking», «ordénalos de mayor a menor», «tabla de posiciones», «los mejores estudiantes»
RANKING = re.compile(r"\b(ranking|rankin|ranquin|clasificacion general|tabla de posiciones|posiciones|"
                     r"ordenad[oa]s? (de|por) (nota|notas|promedio|promedios|calificacion\w*)|"
                     r"orden(ar|alos|a)? (de|por) (nota|notas|promedio|merito)|de mayor a menor|de menor a mayor|"
                     r"de mejor a peor|de peor a mejor|top \d+|los mejores( estudiantes)?|mejores (estudiantes|notas|"
                     r"promedios)|cuadro de honor)\b")
_ASCENDENTE = re.compile(r"\b(de menor a mayor|de peor a mejor|ascendente)\b")

# Actividades pendientes de calificar: «¿qué tareas faltan por calificar?», «qué me falta calificar»
PENDIENTES = re.compile(r"\b(falta(n)? (por |de )?calificar|me falta calificar|faltan calificar|sin calificar|"
                        r"pendientes? (de|por) (calificar|calificacion|revision|revisar)|por calificar|no he calificado|"
                        r"no calificad[oa]s?|que (debo|tengo que) calificar|tareas? por revisar|entregas? por revisar)\b")


# Entregas faltantes / notas cero por estudiante: «¿qué estudiante tiene más tareas sin entregar?»
INCIDENCIAS = re.compile(r"\b(sin entregar|no (ha |han )?entregad[oa]s?|no (ha |han )?entregado|entregas? faltantes?|"
                         r"falta(n)? (de |por )?entregar|mas incidencias|con incidencias|notas? (en )?(cero|0)\b(?!\s*[.,]\d)|"
                         r"ceros|sin entrega|no entreg\w+)")
# Datos que CoraIA no recibe de Moodle UTA (se dice claramente en lugar de responder otra cosa)
NO_DISPONIBLE = re.compile(r"\b(asistencia\w*|asistieron|faltas? (a clase|de asistencia)|inasistencia\w*|horario\w*|"
                           r"atrasos|puntualidad|attendance|schedule\w*)\b")


# Componente de la nota: «mejor promedio en tareas», «el peor en exámenes», «ranking de APE»
_COMPONENTES = [("acd", re.compile(r"\b(examen\w*|evaluacion\w*|pruebas?|acd)\b")),
                ("tareas", re.compile(r"\b(tareas?|deberes|deber)\b")),
                ("pae", re.compile(r"\b(ape|pae|practicas?|proyecto\w*)\b"))]
# Evolución entre unidades: «¿quién mejoró más?», «¿qué estudiante empeoró entre unidades?»
MEJORA = re.compile(r"\b(mejor(o|aron|ado|ando)|ha mejorado|han mejorado|subio|subieron|progres\w*|avanz(o|aron)|"
                    r"repunt\w*|recuper(o|aron))\b")
RETROCESO = re.compile(r"\b(empeor\w*|bajo mas|bajaron|retroced\w*|cayo|cayeron|descendi\w*|decay\w*|"
                       r"se vino abajo)\b")
# Nivel de rendimiento explícito: «¿cuántos están en nivel crítico y quiénes son?», «los aceptables de POO»
_NIVEL = re.compile(r"\b(?:en )?nivel (critico|en riesgo|riesgo|aceptable)\b|\b(?:cuantos|cuantas|quienes|cuales|lista\w*|"
                    r"dame|muestra\w*)\b.*\b(criticos|aceptables)\b")


def componente_pedido(texto: str) -> Optional[str]:
    """'acd' | 'tareas' | 'pae' si la consulta pide un componente concreto de la nota."""
    for clave, patron in _COMPONENTES:
        if patron.search(texto):
            return clave
    return None


def evolucion_pedida(texto: str) -> Optional[str]:
    """'mejora' | 'retroceso' si se pregunta quién mejoró o empeoró (entre unidades)."""
    if RETROCESO.search(texto):
        return "retroceso"
    if MEJORA.search(texto):
        return "mejora"
    return None


def nivel_pedido(texto: str) -> Optional[str]:
    m = _NIVEL.search(texto)
    if not m:
        return None
    valor = m.group(1) or m.group(2)
    return {"critico": "CRITICO", "criticos": "CRITICO", "en riesgo": "EN_RIESGO", "riesgo": "EN_RIESGO",
            "aceptable": "ACEPTABLE", "aceptables": "ACEPTABLE"}[valor]


def orden_ranking(texto: str) -> Optional[str]:
    """'desc' (de mejor a peor, por defecto) | 'asc' si se pide «de menor a mayor»; None si no pide ranking."""
    if not RANKING.search(texto):
        return None
    return "asc" if _ASCENDENTE.search(texto) else "desc"


# ------------------------------------------------------------------ coincidencia parcial de materias
_VACIAS = {"para", "como", "entre", "sobre", "desde", "hasta", "este", "esta", "curso", "materia", "paralelo",
           "nota", "notas", "promedio", "estudiante", "estudiantes", "cual", "cuales", "quien", "quienes", "tiene",
           "dame", "todos", "todas", "mejor", "peor", "general"}


def raiz(palabra: str) -> str:
    """Raíz simple sin plural: «bases» -> «base», «estructuras» -> «estructura»."""
    return palabra[:-1] if len(palabra) >= 5 and palabra.endswith("s") else palabra


def palabras_materia(fullname_normalizado: str) -> set:
    return {raiz(p) for p in re.findall(r"[a-z]{4,}", fullname_normalizado) if p not in _VACIAS}


def cursos_por_nombre(texto: str, cursos: List[Dict[str, Any]], normalizar) -> List[Dict[str, Any]]:
    """
    Cursos cuyo nombre se menciona parcialmente: dos palabras de la materia (o todas, si tiene una sola) o, si nada
    coincide así, una palabra distintiva larga (8+ letras) que sólo aparece en el nombre de ese curso.
    """
    del_texto = {raiz(w) for w in re.findall(r"[a-z]{4,}", texto) if w not in _VACIAS}
    por_curso = {c["id"]: palabras_materia(normalizar(c.get("fullname") or "")) for c in cursos}
    candidatos = [c for c in cursos if por_curso[c["id"]]
                  and len(por_curso[c["id"]] & del_texto) >= min(2, len(por_curso[c["id"]]))]
    if candidatos:
        return candidatos
    unicos = []
    for c in cursos:
        for p in por_curso[c["id"]] & del_texto:
            if len(p) >= 8 and sum(1 for otro in por_curso.values() if p in otro) == 1:
                unicos.append(c)
                break
    return unicos
