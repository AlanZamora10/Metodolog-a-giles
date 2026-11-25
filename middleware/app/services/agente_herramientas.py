"""
Agente conversacional con herramientas — POST /api/v1/agent/chat.

Flujo (RN-15: el cálculo es determinista; la IA sólo decide qué consultar):
  1. Planificación: el microservicio del agente (Ollama llama3.2:1b con *tool calling*) propone qué
     herramientas invocar. Si no responde a tiempo o propone algo inválido, se usa un planificador por
     reglas (intención por palabras clave + curso y estudiante mencionados).
  2. Alcance: el curso explícito del mensaje manda; «todos mis cursos / mis materias / en total» consulta los
     cursos del docente; si se nombra a un estudiante, se consultan todos sus cursos; si no, el curso activo.
  3. Ejecución: cada herramienta consulta datos REALES del sistema (sincronización con Moodle persistida y
     alertas en la base), validando que el curso pertenezca al docente. Cada invocación se registra en
     `logs_sistema` (herramienta, parámetros, docente, origen del plan, filas devueltas).
  4. Respuesta: redactada en español con resumen ejecutivo, viñetas y negritas (Markdown), usando sólo
     los resultados de las herramientas (sin cifras inventadas).
"""

import logging
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from app import repositories
from app.services import agente_idioma as idioma
from app.services import reporte_service, sync_service

logger = logging.getLogger("edumonitor.agente")

AGENT_HOST = os.getenv("AGENT_HOST") or os.getenv("AGENT_URL", "http://agent:8001")
AGENT_TIMEOUT_SECONDS = float(os.getenv("AGENT_INFERENCE_TIMEOUT_SECONDS", "10.0"))
# Presupuesto del plan del LLM en el chat: si Ollama no responde a tiempo se usan las reglas (respuesta en segundos)
AGENT_CHAT_TIMEOUT_SECONDS = float(os.getenv("AGENT_CHAT_TIMEOUT_SECONDS", "6.0"))
# Mensajes de hasta 5 palabras con intención clara se resuelven sin esperar al LLM
MAX_PALABRAS_RAPIDAS = 5
MAX_HERRAMIENTAS_POR_MENSAJE = 4
UMBRAL_APROBACION = 7.0
PLAZO_REFUERZO_DIAS = 7

CATALOGO: Dict[str, Dict[str, Any]] = {
    "listar_cursos_autorizados": {
        "descripcion": "Lista los cursos del docente con estudiantes, promedio y niveles, más los totales "
                       "(cursos, matrículas y estudiantes únicos). Úsala para '¿cuántos cursos/estudiantes tengo?'.",
        "parametros": {},
    },
    "obtener_calificaciones": {
        "descripcion": "Calificaciones ponderadas (Exámenes, Tareas, APE, nota final, nivel, incidencias) de un curso o "
                       "de todos; opcionalmente de un estudiante por nombre, cédula o ID (U-xx) en todos sus cursos, "
                       "o sólo las notas que cumplen un umbral (operador < <= > >= entre, umbral, umbral_max). "
                       "Un nombre de materia es un curso (course_id), nunca un estudiante.",
        "parametros": {"course_id": "integer (opcional)", "estudiante": "string (opcional)",
                       "operador": "< | <= | > | >= | entre (opcional)", "umbral": "number (opcional)",
                       "umbral_max": "number (opcional, sólo con entre)",
                       "extremo": "peor | mejor (opcional: el estudiante con la menor o la mayor nota)"},
    },
    "identificar_alertas": {
        "descripcion": "Alertas tempranas activas (nota crítica o descenso sostenido entre unidades) de un curso o de "
                       "todos.",
        "parametros": {"course_id": "integer (opcional)", "regla": "R1 | R2 (opcional)"},
    },
    "generar_resumen": {
        "descripcion": "Resumen del curso: métricas, distribución de estados, hallazgos y recomendaciones.",
        "parametros": {"course_id": "integer (opcional)"},
    },
    "analizar_actividades": {
        "descripcion": "Rendimiento por actividad (promedio, notas cero, sin entrega, pendientes), ordenado de menor "
                       "a mayor. Úsala para '¿qué actividades tienen menor rendimiento?'.",
        "parametros": {"course_id": "integer (opcional)"},
    },
    "listar_estudiantes": {
        "descripcion": "Nómina de UN curso: cantidad de estudiantes matriculados o lista completa con nombre, "
                       "correo institucional y nota actual. Úsala para '¿cuántos estudiantes tengo en POO?' o "
                       "'lista de estudiantes de ED'.",
        "parametros": {"course_id": "integer", "solo_conteo": "boolean (opcional)"},
    },
    "perfil_docente": {
        "descripcion": "Datos del docente autenticado: nombre completo, correo institucional y cursos asignados. "
                       "Úsala para '¿cómo me llamo?', '¿quién soy?' o '¿qué materias doy?'.",
        "parametros": {},
    },
    "generar_guia_pdf": {
        "descripcion": "Genera la guía oficial de refuerzo UTA - FISEI en PDF de un estudiante (unidad más baja) y "
                       "devuelve el enlace de descarga. Úsala para 'dame el pdf' o 'descargar la guía de X'.",
        "parametros": {"student_query": "string (nombre, cédula o ID U-xx)", "course_id": "integer (opcional)"},
    },
    "proponer_refuerzo": {
        "descripcion": "Analiza las falencias reales de un estudiante y redacta una propuesta de refuerzo (título, "
                       "objetivo, tarea y criterios de evaluación) lista para el Centro de Alertas.",
        "parametros": {"student_query": "string (nombre o ID U-xx del estudiante)", "course_id": "integer (opcional)"},
    },
}

NOMBRE_COMPONENTE = {"acd": "Exámenes", "tareas": "Tareas", "pae": "APE"}
PESO_COMPONENTE = {"acd": 40, "tareas": 30, "pae": 30}
NIVEL_TEXTO = {"CRITICO": "crítico", "EN_RIESGO": "en riesgo", "ACEPTABLE": "aceptable"}
ESTADO_ALERTA_TEXTO = {"ABIERTA": "abierta", "ATENDIDA": "en atención", "PUBLICADO": "refuerzo publicado"}
TENDENCIA_TEXTO = {"SUBE": "al alza", "BAJA": "a la baja", "ESTABLE": "estable"}


class HerramientaError(Exception):
    """Parámetros inválidos o curso no autorizado."""


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto.lower()).strip()


_TILDES = {"programacion": "programación", "metodologias": "metodologías", "agiles": "ágiles",
           "configuracion": "configuración", "informatica": "informática", "ingenieria": "ingeniería",
           "analisis": "análisis", "logica": "lógica", "matematica": "matemática", "computacion": "computación"}


_ROMANOS = {"i", "ii", "iii", "iv", "v", "vi"}  # materias seriadas: «Ingeniería de software I»


def _nombre_curso(fullname: str) -> str:
    """'(SOF) PROGRAMACION ORIENTADA A OBJETOS - A' -> 'Programación orientada a objetos, paralelo A'."""
    nombre = re.sub(r"^\(\w+\)\s*", "", fullname or "").strip()
    paralelo = re.search(r"\s+-\s+([A-Z])$", nombre)
    if paralelo:
        nombre = nombre[:paralelo.start()]
    nombre = " ".join(p.upper() if p in _ROMANOS else _TILDES.get(p, p) for p in nombre.lower().split())
    nombre = nombre[:1].upper() + nombre[1:]
    return f"{nombre}, paralelo {paralelo.group(1)}" if paralelo else nombre


def _sin_codigos(texto: str, cursos: List[Dict[str, Any]]) -> str:
    """La respuesta al docente usa el nombre de la materia, no el código interno del curso (SOF-POO-A)."""
    for c in sorted(cursos, key=lambda x: len(x["shortname"]), reverse=True):
        nombre = idioma.curso_en(c["fullname"]) if idioma.IDIOMA.get() == "en" else _nombre_curso(c["fullname"])
        texto = texto.replace(c["shortname"], nombre)
    return texto


def _unidad(clave: Optional[str]) -> str:
    return f"Unidad {clave[1:]}" if clave and clave.startswith("U") else (clave or "—")


def _f(valor: Optional[float]) -> str:
    return "—" if valor is None else f"{valor:.2f}"


def _incidencia(a: Dict[str, Any]) -> Optional[str]:
    if a["estado"] == "SIN_ENTREGA":
        return "SIN_ENTREGA"
    if a["estado"] == "PENDIENTE":
        return "PENDIENTE"
    if a["nota"] == 0:
        return "NOTA_0"
    return None


_INCIDENCIA_TEXTO = {"SIN_ENTREGA": "sin entrega", "PENDIENTE": "pendiente de calificación", "NOTA_0": "nota 0"}


# =============================================================================== Herramientas
def _cursos(docente: dict, course_id: Optional[int]) -> List[Dict[str, Any]]:
    propios = sync_service.cursos_del_docente(docente["email"])
    if course_id is None:
        return propios
    curso = next((c for c in propios if c["id"] == int(course_id)), None)
    if curso is None:
        raise HerramientaError(f"El curso {course_id} no existe o no pertenece al docente.")
    return [curso]


def _coincide(e: Dict[str, Any], filtro: str) -> bool:
    """Código U-xx, cédula o nombre: basta con parte del nombre completo («Carlos Mendoza» encuentra a
    «Carlos Andrés Mendoza Paredes») siempre que cada palabra buscada esté en el nombre."""
    nombre = _normalizar(e["nombres"] or "")
    buscadas, palabras = filtro.split(), nombre.split()
    return (filtro == _normalizar(e["id_number"]) or filtro == (e.get("cedula") or "") or filtro in nombre
            or (bool(buscadas) and all(p in palabras for p in buscadas)))


def listar_cursos_autorizados(docente: dict) -> Dict[str, Any]:
    propios = sync_service.cursos_del_docente(docente["email"])
    cursos = [sync_service.resumen_curso(c) for c in propios]
    unicos = {e["id_number"] for c in propios for e in c["estudiantes"]}
    return {
        "cursos": cursos,
        "totales": {"cursos": len(cursos), "matriculas": sum(c["total_estudiantes"] for c in cursos),
                    "estudiantes_unicos": len(unicos),
                    "criticos": sum(c["criticos"] for c in cursos), "en_riesgo": sum(c["en_riesgo"] for c in cursos)},
        "filas": len(cursos),
    }


def listar_estudiantes(docente: dict, course_id: Optional[int] = None, solo_conteo: Any = False) -> Dict[str, Any]:
    """Nómina de un solo curso del docente (cantidad o lista completa con correo y nota actual)."""
    if not course_id:
        raise HerramientaError("indique la materia (por ejemplo, POO o Estructura de datos).")
    [curso] = _cursos(docente, course_id)
    estudiantes = sorted(curso["estudiantes"], key=lambda e: _normalizar(e["nombres"] or ""))
    return {
        "curso": {"id": curso["id"], "shortname": curso["shortname"], "fullname": curso["fullname"]},
        "total": len(estudiantes),
        "solo_conteo": str(solo_conteo).lower() in ("1", "true", "si", "sí"),
        "estudiantes": [{"id_number": e["id_number"], "nombres": e["nombres"], "email": e.get("email"),
                         "nota_final": e["nota_final"], "nivel_riesgo": e["nivel_riesgo"]} for e in estudiantes],
        "filas": len(estudiantes),
    }


def perfil_docente(docente: dict) -> Dict[str, Any]:
    """Perfil del docente autenticado con sus cursos asignados (datos de la sesión y de la sincronización)."""
    cursos = sync_service.cursos_del_docente(docente["email"])
    return {
        "nombres": docente.get("nombres"), "email": docente.get("email"), "cedula": docente.get("cedula"),
        "cursos": [{"id": c["id"], "shortname": c["shortname"], "fullname": c["fullname"],
                    "total_estudiantes": len(c["estudiantes"])} for c in cursos],
        "filas": len(cursos),
    }


OPERADORES_NOTA = {"<": "menor a", "<=": "menor o igual a", ">": "mayor a", ">=": "mayor o igual a",
                   "entre": "entre"}


def _criterio_valido(operador: Optional[str], umbral: Any, umbral_max: Any) -> Optional[Dict[str, Any]]:
    """Normaliza el criterio numérico (escala 0-10); None si no hay criterio o es inválido."""
    if operador not in OPERADORES_NOTA or umbral in (None, ""):
        return None
    try:
        valor = float(str(umbral).replace(",", "."))
        maximo = float(str(umbral_max).replace(",", ".")) if operador == "entre" else None
    except (TypeError, ValueError):
        return None
    if operador == "entre":
        if maximo is None:
            return None
        valor, maximo = min(valor, maximo), max(valor, maximo)
    if not (0 <= valor <= 10) or (maximo is not None and not 0 <= maximo <= 10):
        return None
    return {"operador": operador, "umbral": valor, **({"umbral_max": maximo} if maximo is not None else {})}


def _cumple(nota: Optional[float], criterio: Dict[str, Any]) -> bool:
    if nota is None:
        return False
    nota, u = round(float(nota), 2), criterio["umbral"]
    return {"<": nota < u, "<=": nota <= u, ">": nota > u, ">=": nota >= u,
            "entre": criterio["operador"] == "entre" and u <= nota <= criterio.get("umbral_max", u)}[criterio["operador"]]


def texto_criterio(criterio: Dict[str, Any]) -> str:
    """'nota menor a 4.00' / 'nota entre 4.00 y 6.00'."""
    if criterio["operador"] == "entre":
        return f"nota entre {criterio['umbral']:.2f} y {criterio['umbral_max']:.2f}"
    return f"nota {OPERADORES_NOTA[criterio['operador']]} {criterio['umbral']:.2f}"


def obtener_calificaciones(docente: dict, course_id: Optional[int] = None, estudiante: Optional[str] = None,
                           operador: Optional[str] = None, umbral: Any = None,
                           umbral_max: Any = None, extremo: Optional[str] = None) -> Dict[str, Any]:
    """`extremo` = 'peor' | 'mejor': ordena para destacar al estudiante con la menor o la mayor nota."""
    filtro = _normalizar(estudiante) if estudiante else None
    extremo = extremo if extremo in ("peor", "mejor") else None
    criterio = _criterio_valido(operador, umbral, umbral_max)
    cursos = _cursos(docente, course_id)
    resultado = []
    for c in cursos:
        for e in c["estudiantes"]:
            if filtro and not _coincide(e, filtro):
                continue
            if criterio and not _cumple(e["nota_final"], criterio):
                continue
            resultado.append({
                "curso_id": c["id"], "curso": c["shortname"], "curso_nombre": c["fullname"],
                "id_number": e["id_number"], "nombres": e["nombres"], "cedula": e.get("cedula"),
                "acd": e["acd"], "tareas": e["tareas"], "pae": e["pae"], "nota_final": e["nota_final"],
                "nivel_riesgo": e["nivel_riesgo"], "tendencia": e.get("tendencia"),
                "promedios_unidad": e.get("promedios_unidad") or {},
                "incidencias": [f"{a['id_number']} {_incidencia(a)}" for a in e["actividades"] if _incidencia(a)],
            })
    if filtro and not resultado and not criterio:
        raise HerramientaError(f"no encontré a «{estudiante}» entre sus estudiantes. Pruebe con su nombre "
                               "completo o su cédula.")
    if criterio or extremo == "peor":
        resultado.sort(key=lambda f: (f["nota_final"], f["nombres"]))
    elif extremo == "mejor":
        resultado.sort(key=lambda f: (-f["nota_final"], f["nombres"]))
    return {"calificaciones": resultado, "filas": len(resultado), "estudiante": estudiante, "criterio": criterio,
            "extremo": extremo,
            "cursos_consultados": [{"id": c["id"], "shortname": c["shortname"], "fullname": c["fullname"]}
                                   for c in cursos]}


def identificar_alertas(docente: dict, course_id: Optional[int] = None, regla: Optional[str] = None) -> Dict[str, Any]:
    ids = {c["id"] for c in _cursos(docente, course_id)}
    codigo_regla = {"R1": "R1_NOTA_CRITICA", "R2": "R2_DESCENSO"}.get((regla or "").upper()[:2])
    alertas = [
        {"id": a["id"], "curso": a["curso_codigo"], "curso_id": a["curso_id"], "id_number": a["id_number"],
         "nombres": a["nombres"], "regla": a["regla"], "nota_final": a.get("nota_final"),
         "pendiente": a.get("pendiente"), "estado": a["estado"], "evidencia": a.get("evidencia")}
        for a in repositories.list_alertas()
        if a.get("curso_id") in ids and a["estado"] in ("ABIERTA", "ATENDIDA", "PUBLICADO")
        and (codigo_regla is None or a["regla"] == codigo_regla)
    ]
    return {"alertas": alertas, "filas": len(alertas), "regla": codigo_regla}


def generar_resumen(docente: dict, course_id: Optional[int] = None) -> Dict[str, Any]:
    resumenes = []
    for c in _cursos(docente, course_id):
        r = reporte_service.construir_reporte(c, repositories.list_alertas(course_id=c["id"]),
                                              sync_service.SYNC_STATE.get("ultima_sincronizacion"))
        resumenes.append({"curso": c["shortname"], "curso_id": c["id"], "curso_nombre": c["fullname"],
                          "metricas": r["metricas"], "distribucion_estados": r["distribucion_estados"],
                          "hallazgos": r["hallazgos"], "recomendaciones": r["recomendaciones"]})
    return {"resumenes": resumenes, "filas": len(resumenes)}


def analizar_actividades(docente: dict, course_id: Optional[int] = None) -> Dict[str, Any]:
    """Rendimiento por actividad (promedio de las notas que cuentan e incidencias), de menor a mayor."""
    actividades = []
    for c in _cursos(docente, course_id):
        por_actividad: Dict[str, Dict[str, Any]] = {}
        for e in c["estudiantes"]:
            for a in e["actividades"]:
                fila = por_actividad.setdefault(a["id_number"], {
                    "curso": c["shortname"], "curso_id": c["id"], "actividad": a["id_number"],
                    "nombre": a.get("nombre") or a["id_number"], "componente": a["componente"], "unidad": a["unidad"],
                    "notas": [], "ceros": 0, "sin_entrega": 0, "pendientes": 0,
                })
                incidencia = _incidencia(a)
                if incidencia == "SIN_ENTREGA":
                    fila["sin_entrega"] += 1
                elif incidencia == "PENDIENTE":
                    fila["pendientes"] += 1
                elif incidencia == "NOTA_0":
                    fila["ceros"] += 1
                if a["nota"] is not None:
                    fila["notas"].append(a["nota"])
        for fila in por_actividad.values():
            notas = fila.pop("notas")
            fila["calificaciones"] = len(notas)
            fila["promedio"] = round(sum(notas) / len(notas), 2) if notas else None
            fila["bajo_aprobacion"] = sum(1 for n in notas if n < UMBRAL_APROBACION)
            actividades.append(fila)
    actividades.sort(key=lambda f: (f["promedio"] is None, f["promedio"] if f["promedio"] is not None else 99,
                                    f["curso"], f["actividad"]))
    return {"actividades": actividades, "filas": len(actividades)}


def _curso_para_refuerzo(registros: List[Tuple[Dict[str, Any], Dict[str, Any]]],
                         course_id: Optional[int]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if course_id is not None:
        for curso, e in registros:
            if curso["id"] == int(course_id):
                return curso, e
    return min(registros, key=lambda r: r[1]["nota_final"])


def proponer_refuerzo(docente: dict, student_query: Optional[str] = None,
                      course_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Propuesta de refuerzo a partir de las falencias REALES del estudiante: unidad y componente más bajos,
    actividades con nota 0, sin entrega o pendientes y las actividades calificadas con menor nota.
    Si se indica un curso del docente en el que el estudiante está matriculado se usa ese; si no, el curso
    donde el estudiante tiene la nota más baja.
    """
    if not student_query:
        raise HerramientaError("Indique el estudiante (nombre o ID U-xx) para preparar el refuerzo.")
    filtro = _normalizar(student_query)
    registros = [(c, e) for c in _cursos(docente, None) for e in c["estudiantes"] if _coincide(e, filtro)]
    if course_id is not None:
        _cursos(docente, course_id)  # valida que el curso sea del docente
    if not registros:
        raise HerramientaError(f"No se encontró al estudiante «{student_query}» en sus cursos.")
    curso, e = _curso_para_refuerzo(registros, course_id)

    unidades = {u: v for u, v in (e.get("promedios_unidad") or {}).items() if v is not None}
    unidad_critica = min(unidades, key=unidades.get) if unidades else None
    componentes = {k: e[k] for k in ("acd", "tareas", "pae") if e.get(k) is not None}
    componente_debil = min(componentes, key=componentes.get) if componentes else None
    incidencias = [{"actividad": a["id_number"], "nombre": a.get("nombre") or a["id_number"], "tipo": _incidencia(a)}
                   for a in e["actividades"] if _incidencia(a)]
    calificadas = sorted((a for a in e["actividades"] if a["nota"] is not None and a["estado"] == "CALIFICADO"
                          and a["nota"] > 0), key=lambda a: a["nota"])[:3]
    alerta = next((a for a in repositories.list_alertas(course_id=curso["id"])
                   if a["id_number"] == e["id_number"] and a["estado"] in ("ABIERTA", "ATENDIDA", "PUBLICADO")), None)

    num_unidad = unidad_critica[1:] if unidad_critica else None
    en_unidad = [a for a in e["actividades"] if num_unidad and str(a["unidad"]) == num_unidad]
    foco_act = (next((a for a in en_unidad if _incidencia(a) in ("SIN_ENTREGA", "NOTA_0")), None)
                or min((a for a in en_unidad if a["nota"] is not None), key=lambda a: a["nota"], default=None)
                or (calificadas[0] if calificadas else None))
    foco = foco_act.get("nombre") if foco_act else None
    titulo = (f"Refuerzo Unidad {num_unidad}" if num_unidad else "Refuerzo académico") + \
             (f": {foco.split(':')[-1].strip()}" if foco else "") + f" — {_nombre_curso(curso['fullname'])}"

    objetivo = (f"Que {e['nombres']} consolide los aprendizajes de la Unidad {num_unidad} "
                f"(promedio actual {_f(unidades[unidad_critica])}/10)" if unidad_critica
                else f"Que {e['nombres']} consolide los aprendizajes evaluados del curso")
    if componente_debil:
        objetivo += f", fortalezca el componente {NOMBRE_COMPONENTE[componente_debil]} ({_f(componentes[componente_debil])}/10)"
    pendientes_entrega = [i for i in incidencias if i["tipo"] in ("SIN_ENTREGA", "NOTA_0")]
    if pendientes_entrega:
        objetivo += (f" y regularice {idioma.plural(len(pendientes_entrega), 'entrega', 'entregas')} con nota 0 o "
                     "sin entrega")
    objetivo += f", alcanzando al menos {UMBRAL_APROBACION:.2f}/10 en esta actividad."

    pasos = []
    if calificadas:
        pasos.append("Revise el material y la retroalimentación de: " + "; ".join(
            f"{a['id_number']} «{a.get('nombre') or a['id_number']}» ({_f(a['nota'])}/10)" for a in calificadas) + ".")
    if pendientes_entrega:
        pasos.append("Desarrolle y entregue nuevamente: " + "; ".join(
            f"{i['actividad']} «{i['nombre']}» ({_INCIDENCIA_TEXTO[i['tipo']]})" for i in pendientes_entrega) + ".")
    pasos.append(f"Resuelva una guía de ejercicios de la Unidad {num_unidad}" if num_unidad else "Resuelva una guía de ejercicios")
    pasos[-1] += (f" enfocada en el componente {NOMBRE_COMPONENTE[componente_debil]}, explicando el procedimiento de cada "
                  f"ejercicio." if componente_debil else ", explicando el procedimiento de cada ejercicio.")
    pasos.append("Suba a Moodle UTA un documento PDF con el desarrollo y una reflexión breve sobre los errores "
                 "detectados y cómo los corrigió.")

    criterios = [
        {"criterio": "Corrección técnica de los ejercicios resueltos", "peso": 40},
        {"criterio": f"Dominio de los temas de la Unidad {num_unidad}" if num_unidad else "Dominio de los temas evaluados",
         "peso": 30},
        {"criterio": "Regularización de las entregas pendientes" if pendientes_entrega
         else "Aplicación a un caso práctico del curso", "peso": 20},
        {"criterio": "Presentación y reflexión sobre los errores", "peso": 10},
    ]
    instrucciones = (
        f"Objetivo: {objetivo}\n\nDescripción de la tarea:\n"
        + "\n".join(f"{i}. {p}" for i, p in enumerate(pasos, 1))
        + "\n\nCriterios de evaluación:\n" + "\n".join(f"- {c['criterio']} ({c['peso']} %)" for c in criterios)
        + f"\n\nPlazo sugerido: {PLAZO_REFUERZO_DIAS} días."
    )
    return {
        "estudiante": {"id_number": e["id_number"], "nombres": e["nombres"], "email": e.get("email")},
        "curso": curso["shortname"], "curso_id": curso["id"], "curso_nombre": curso["fullname"],
        "otros_cursos": [{"curso": c["shortname"], "nota_final": est["nota_final"]} for c, est in registros
                         if c["id"] != curso["id"]],
        "evidencia": {"nota_final": e["nota_final"], "nivel_riesgo": e["nivel_riesgo"], "unidad_critica": unidad_critica,
                      "promedio_unidad_critica": unidades.get(unidad_critica) if unidad_critica else None,
                      "componente_debil": componente_debil,
                      "promedio_componente_debil": componentes.get(componente_debil) if componente_debil else None,
                      "incidencias": incidencias,
                      "actividades_mas_bajas": [{"actividad": a["id_number"], "nota": a["nota"]} for a in calificadas]},
        "propuesta": {"titulo": titulo[:200], "objetivo": objetivo, "pasos": pasos, "criterios": criterios,
                      "plazo_dias": PLAZO_REFUERZO_DIAS, "instrucciones": instrucciones},
        "alerta": ({"id": alerta["id"], "estado": alerta["estado"], "regla": alerta["regla"]} if alerta else None),
        "filas": 1,
    }


def hora_ecuador(valor: Any) -> datetime:
    """Fecha guardada en la base (UTC, con o sin zona) -> hora local de Ecuador (UTC-5) sin zona."""
    fecha = valor if isinstance(valor, datetime) else datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone(timedelta(hours=-5))).replace(tzinfo=None)


def guia_de_estudiante(docente: dict, student_query: Optional[str],
                       course_id: Optional[int] = None) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Datos para la guía oficial de refuerzo (PDF) de un estudiante del docente: curso (el indicado si está
    matriculado; si no, el de nota más baja), unidad con el promedio más bajo y fecha de entrega (la del refuerzo
    publicado o, si no hay, dentro del plazo sugerido). Devuelve (datos para generar_guia_pdf, curso, estudiante).
    """
    if not student_query:
        raise HerramientaError("Indique el estudiante (nombre, cédula o ID U-xx) para generar la guía en PDF.")
    filtro = _normalizar(student_query)
    registros = [(c, e) for c in _cursos(docente, None) for e in c["estudiantes"] if _coincide(e, filtro)]
    if course_id is not None:
        _cursos(docente, course_id)  # valida que el curso sea del docente
    if not registros:
        raise HerramientaError(f"No se encontró al estudiante «{student_query}» en sus cursos.")
    curso, e = _curso_para_refuerzo(registros, course_id)
    unidades = {u: v for u, v in (e.get("promedios_unidad") or {}).items() if v is not None}
    unidad = min(unidades, key=unidades.get) if unidades else "U1"
    vence = (datetime.now() + timedelta(days=PLAZO_REFUERZO_DIAS)).replace(hour=23, minute=59, second=0, microsecond=0)
    for alerta in repositories.list_alertas(course_id=curso["id"]):
        refuerzo = repositories.get_refuerzo(alerta_id=alerta["id"]) if alerta["id_number"] == e["id_number"] else None
        if refuerzo and refuerzo.get("fecha_entrega"):   # refuerzo ya publicado: su fecha real en Moodle
            publicada = hora_ecuador(refuerzo["fecha_entrega"])
            if publicada > datetime.now():               # uno ya vencido (parcial anterior) no fija la entrega
                vence = publicada
    datos = {
        "estudiante": {"nombres": e["nombres"], "email": e.get("email"), "id_number": e["id_number"],
                       "cedula": e.get("cedula")},
        "curso": curso, "unidad": f"Unidad {unidad[1:]}", "docente": docente.get("nombres") or docente["email"],
        "titulo": f"Refuerzo Unidad {unidad[1:]} — {curso['shortname']}", "instrucciones": "",
        "fecha_entrega": vence, "registro": e,
    }
    return datos, curso, e


def generar_guia_pdf(docente: dict, student_query: Optional[str] = None,
                     course_id: Optional[int] = None) -> Dict[str, Any]:
    """Guía oficial UTA - FISEI del estudiante, lista para descargar desde el chat (GET /agent/guia-pdf)."""
    from app.services import guia_pdf  # evita importación circular (guia_pdf usa _nombre_curso)
    datos, curso, e = guia_de_estudiante(docente, student_query, course_id)
    guia = guia_pdf.construir_guia(**datos)
    nombre = guia_pdf.nombre_archivo(guia)
    return {
        "estudiante": {"id_number": e["id_number"], "nombres": e["nombres"]},
        "curso": curso["shortname"], "curso_id": curso["id"], "curso_nombre": curso["fullname"],
        "unidad": guia["unidad_titulo"], "fecha_entrega": datos["fecha_entrega"].isoformat(timespec="minutes"),
        "descarga": {"tipo": "pdf", "nombre": nombre, "etiqueta": "Descargar guía PDF",
                     "url": f"/api/v1/agent/guia-pdf?id_number={e['id_number']}&course_id={curso['id']}"},
        "filas": 1,
    }


EJECUTORES: Dict[str, Callable[..., Dict[str, Any]]] = {
    "listar_cursos_autorizados": listar_cursos_autorizados,
    "obtener_calificaciones": obtener_calificaciones,
    "identificar_alertas": identificar_alertas,
    "generar_resumen": generar_resumen,
    "analizar_actividades": analizar_actividades,
    "proponer_refuerzo": proponer_refuerzo,
    "listar_estudiantes": listar_estudiantes,
    "perfil_docente": perfil_docente,
    "generar_guia_pdf": generar_guia_pdf,
}
_PARAMETROS_VALIDOS = {
    "listar_cursos_autorizados": set(),
    "obtener_calificaciones": {"course_id", "estudiante", "operador", "umbral", "umbral_max", "extremo"},
    "identificar_alertas": {"course_id", "regla"},
    "generar_resumen": {"course_id"},
    "analizar_actividades": {"course_id"},
    "proponer_refuerzo": {"student_query", "course_id"},
    "listar_estudiantes": {"course_id", "solo_conteo"},
    "perfil_docente": set(),
    "generar_guia_pdf": {"student_query", "course_id"},
}


# =============================================================================== Planificación
_GLOBAL = re.compile(r"\b(mis (\d+|dos|tres|cuatro|cinco) (cursos|materias|asignaturas)|todas? (mis |las |los )?"
                     r"(materias|cursos|asignaturas)|mis cursos|mis materias|mis asignaturas|en total|en general|global|"
                     r"todos mis|cada (curso|materia)|entre (mis )?cursos|(resumen|panorama|informe|reporte) general)\b")
_REFUERZO = re.compile(r"\b(refuerzo|reforzar|plan de mejora|plan de estudios?|plan de apoyo|plan de accion|"
                       r"recuperacion|nivelacion|actividad de apoyo|apoyo academico|tutoria|"
                       r"como (le |lo |la )?(puedo )?(ayudar\w*|apoyar\w*)|ayudarl[oae]s?|apoyarl[oae]s?|"
                       r"prepar\w* (una |un )?(actividad|tarea|plan))\b")
_ACTIVIDADES = re.compile(r"\b((actividad|actividades|tarea|tareas|evaluacion|evaluaciones)\b.*\b(menor|bajo|baja|"
                          r"peor|peores|dificil\w*|problema\w*|rendimiento|cuesta)|(menor|peor|bajo) rendimiento)")
# Umbral numérico explícito sobre la nota («nota menor de 4 puntos», «promedio mayor a 8», «entre 4 y 6»)
_NUMEROS_TEXTO = {"cero": "0", "uno": "1", "una": "1", "dos": "2", "tres": "3", "cuatro": "4", "cinco": "5",
                  "seis": "6", "siete": "7", "ocho": "8", "nueve": "9", "diez": "10"}
_NUM = r"(\d{1,2}(?:[.,]\d{1,2})?)"
_CONTEXTO_NOTA = re.compile(r"\b(nota|notas|promedio|promedios|calificacion\w*|puntos?|puntaje|sobre 10)\b|/10")
_PATRONES_UMBRAL = [
    ("entre", re.compile(rf"\bentre\s+{_NUM}\s+(?:y|a)\s+{_NUM}")),
    ("<=", re.compile(rf"(?:\b(?:menor|menores|inferior|inferiores)\s+o\s+igual(?:es)?\s+(?:a|que|de)|<=|\bcomo\s+maximo|"
                      rf"\bmaximo\s+de)\s*{_NUM}")),
    (">=", re.compile(rf"(?:\b(?:mayor|mayores|superior|superiores)\s+o\s+igual(?:es)?\s+(?:a|que|de)|>=|\bal\s+menos|"
                      rf"\bcomo\s+minimo|\bminimo\s+de)\s*{_NUM}")),
    ("<", re.compile(rf"(?:\b(?:menor|menores|inferior|inferiores)\s+(?:a|que|de)|\bmenos\s+de|\bpor\s+debajo\s+de|"
                     rf"\bbajo|<)\s*{_NUM}")),
    (">", re.compile(rf"(?:\b(?:mayor|mayores|superior|superiores)\s+(?:a|que|de)|\bmas\s+de|\bpor\s+encima\s+de|"
                     rf"\bsobre|>)\s*{_NUM}(?!\s*/)")),
]


def criterio_nota(texto: str) -> Optional[Dict[str, Any]]:
    """Criterio numérico explícito del mensaje (texto normalizado), o None."""
    if not _CONTEXTO_NOTA.search(texto):
        return None
    texto = re.sub(r"\b(" + "|".join(_NUMEROS_TEXTO) + r")\b", lambda m: _NUMEROS_TEXTO[m.group(1)], texto)
    for operador, patron in _PATRONES_UMBRAL:
        m = patron.search(texto)
        if m:
            criterio = _criterio_valido(operador, m.group(1), m.group(2) if operador == "entre" else None)
            if criterio:
                return criterio
    return None


# Frases cortas e informales con intención directa (se resuelven sin LLM)
_PANORAMA = re.compile(r"\b(como (van|va|estan|esta|andan|anda) (mis |los |todos (mis |los )?)?(cursos|materias|"
                       r"asignaturas|paralelos|estudiantes|alumnos|clases)|resumen general|panorama( general)?|"
                       r"vista general|estado general)\b")
_EN_PROBLEMAS = re.compile(r"\b(quien(es)? (esta|estan|va|van|anda|andan) (mal|en riesgo|bajo|bajos)|"
                           r"quien(es)? (necesita|necesitan|requiere|requieren) (ayuda|atencion|apoyo)|"
                           r"(estudiantes|alumnos) (en riesgo|criticos|con problemas|que van mal)|hay alertas?|"
                           r"alertas? (activas|pendientes|abiertas)|peores (notas|estudiantes|alumnos)|van mal|esta mal|"
                           r"(tienen|tiene|con|presentan|presenta) (problemas|dificultades|bajo rendimiento))\b")
_REPROBADOS = re.compile(r"\b(reprob\w*|desaprob\w*|no aprueban|no aprobados|perdiendo|pierden|jalad\w*)\b")
_APROBADOS = re.compile(r"\b(aprobados|aprueban|aprobando)\b")


def _criterio_informal(texto: str) -> Optional[Dict[str, Any]]:
    """«reprobados» = nota menor a 7.00; «aprobados» = nota mayor o igual a 7.00 (umbral de aprobación)."""
    if _REPROBADOS.search(texto):
        return {"operador": "<", "umbral": UMBRAL_APROBACION}
    if _APROBADOS.search(texto):
        return {"operador": ">=", "umbral": UMBRAL_APROBACION}
    return None


# Nómina de una materia («lista completa de POO», «quiénes están en ED»; tolera «lsita», «listdo»)
_NOMINA = re.compile(r"\b(quien(es)? (esta|estan|son|hay|forman|conforman|integran) (en|de)|nomina|nombres y apellidos|"
                     r"nombre completo|matriculados|integrantes)\b")
# Si la frase pide seguimiento (riesgo, alertas...), no es una nómina aunque mencione «estudiantes de POO»
_NO_ES_NOMINA = re.compile(r"\b(riesgo|atencion|alerta\w*|mal|critic\w*|reprob\w*|problema\w*|ayuda|dificultad\w*|"
                           r"refuerzo|resumen|actividad\w*)\b")
_CONTEO = re.compile(r"\b(cuant[oa]s (estudiantes|alumnos|matriculados|personas|chicos)|numero de (estudiantes|alumnos)|"
                     r"cantidad de (estudiantes|alumnos)|total de (estudiantes|alumnos))\b")
_PALABRAS_LISTA = ("lista", "listado", "listar", "listame", "nomina", "enlista")
# Perfil del docente autenticado
_PERFIL = re.compile(r"\b(como me llamo|cual es mi nombre|mi nombre|quien soy( yo)?|mis datos|mi perfil|"
                     r"que (materias|cursos|asignaturas) (doy|dicto|imparto|tengo asignad\w*|enseno)|"
                     r"(materias|cursos|asignaturas) (que )?(doy|dicto|imparto))\b")
# Lenguaje inapropiado: respuesta breve y profesional
_INSULTOS = {"inutil", "idiota", "estupido", "estupida", "tonto", "tonta", "imbecil", "basura", "mierda", "maldito",
             "maldita", "pendejo", "pendeja", "carajo", "verga", "puta", "puto", "porqueria", "callate", "odio",
             "baboso", "babosa", "burro", "inservible", "mamon", "huevon", "cojudo", "gil",
             # en inglés
             "useless", "stupid", "idiot", "dumb", "moron", "trash", "garbage", "sucks", "shut"}
_TECLADO = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
_RESPUESTA_INSTITUCIONAL_EN = ("I'm CoraIA, the academic assistant of FISEI. I can help you with your **courses**, "
                               "your students' **grades** or **early alerts**. What do you need to check?")
_RESPUESTA_INSTITUCIONAL = ("Soy CoraIA, el asistente académico de la FISEI. Puedo ayudarle con sus "
                            "**cursos**, las **notas** de sus estudiantes o las **alertas tempranas**. "
                            "¿Qué necesita consultar?")


def _pide_lista(texto: str) -> bool:
    """«lista», «listado» o «nómina», tolerando una letra cambiada u omitida («lsita», «listdo»)."""
    if _NO_ES_NOMINA.search(texto):
        return False
    if _NOMINA.search(texto):
        return True
    return any(w == p or (len(w) >= 4 and w[0] == p[0] and SequenceMatcher(None, w, p).ratio() >= 0.75)
               for w in re.findall(r"[a-z]+", texto) for p in _PALABRAS_LISTA)


def fuera_de_contexto(texto: str) -> Optional[str]:
    """'inapropiado' (insultos), 'sin_sentido' (texto aleatorio) o None (texto normalizado)."""
    palabras = re.findall(r"[a-z]+", texto)
    if any(p in _INSULTOS for p in palabras) or re.search(r"\b(no sirves|no sirve para nada|eres un asco)\b", texto):
        return "inapropiado"
    if re.search(r"\d", texto) or not palabras:
        return None

    def rara(p: str) -> bool:
        return (not re.search(r"[aeiou]", p) or bool(re.search(r"[^aeiou\s]{4,}", p))
                or (len(p) >= 3 and any(p in fila for fila in _TECLADO)))

    return "sin_sentido" if all(rara(p) for p in palabras) else None


# Pregunta en singular por un extremo: «el estudiante con la peor calificación de POO», «quién tiene la mejor nota»,
# «el mejor alumno de ED», «el estudiante con la nota más baja». («las peores notas», en plural, son alertas.)
_EXTREMO = re.compile(
    r"\b(?:(?:el|la|al) (?:estudiante|alumn[oa]) (?:con|que tiene|de) (?:la |el )?|quien tiene (?:la |el )?|"
    r"(?:el|la) )(?P<adj>peor|menor|mejor|mayor|mas baja|mas bajo|mas alta|mas alto) "
    r"(?:nota|calificacion|promedio|rendimiento|desempeno|estudiante|alumn[oa])\b"
    r"|\b(?:(?:estudiante|alumn[oa]) con |quien tiene |cual es )?(?:la |el )(?:nota|calificacion|promedio) "
    r"(?P<adj2>mas baja|mas bajo|mas alta|mas alto)\b")


def extremo_pedido(texto: str) -> Optional[str]:
    """'peor' | 'mejor' si se pregunta por EL estudiante con la menor / mayor nota."""
    m = _EXTREMO.search(texto)
    if not m:
        return None
    adjetivo = m.group("adj") or m.group("adj2")
    return "peor" if adjetivo in ("peor", "menor", "mas baja", "mas bajo") else "mejor"


# Guía oficial en PDF: «perfecto dame el pdf», «descargar pdf», «genera el pdf de ese plan», «descarga la guía de X»
_PIDE_PDF = re.compile(r"\bpdf\b|\bdescarg\w*\b.*\bguia\b")


def estudiante_en_contexto(docente: dict) -> Optional[Dict[str, Any]]:
    """Último estudiante consultado en el chat (30 min): «dame el pdf» se refiere a él."""
    for log in repositories.chats_recientes(docente["email"]):
        previo = (log.get("detalle") or {}).get("estudiante_contexto")
        if previo:
            return previo
    return None


def _estudiante_de(usadas: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Estudiante sobre el que trató la respuesta (plan de apoyo, guía PDF o calificaciones de una persona)."""
    for u in reversed(usadas):
        r = u["resultado"]
        if "error" in r:
            continue
        if u["herramienta"] in ("proponer_refuerzo", "generar_guia_pdf"):
            return {"nombres": r["estudiante"]["nombres"], "course_id": r["curso_id"]}
        if u["herramienta"] == "obtener_calificaciones" and r.get("estudiante") and r["calificaciones"]:
            filas = r["calificaciones"]
            return {"nombres": filas[0]["nombres"], "course_id": filas[0]["curso_id"] if len(filas) == 1 else None}
    return None


def _intencion_directa(texto: str) -> bool:
    return bool(_PIDE_PDF.search(texto) or _PANORAMA.search(texto) or _EN_PROBLEMAS.search(texto)
                or _criterio_informal(texto) or extremo_pedido(texto) or criterio_nota(texto) or _PERFIL.search(texto) or _CONTEO.search(texto) or _pide_lista(texto))


_CURSOS = re.compile(r"\b(mis cursos|que cursos|cuales cursos|cursos tengo|lista de cursos|listar cursos|"
                     r"cuantos cursos|cuantos estudiantes|cuantos alumnos|cuantas materias|materias tengo)\b")


# Saludos y cortesías: respuesta breve sin herramientas (no se lanzan consultas ni informes).
_VOCABULARIO_CORTESIA = {
    "hola", "holi", "hey", "buenas", "buenos", "buen", "dia", "dias", "tardes", "noches", "saludos", "que", "tal",
    "como", "estas", "esta", "gracias", "muchas", "mil", "muy", "amable", "ok", "okay", "oki", "vale", "listo",
    "perfecto", "genial", "excelente", "entendido", "de", "acuerdo", "chao", "adios", "hasta", "luego", "pronto",
    "manana", "nos", "vemos", "bien", "profe", "agente", "asistente", "edumonitor", "y", "tu", "usted",
    "por", "favor", "porfa", "excelentes", "super", "gracias", "dale", "bueno", "muy", "si", "claro",
    "te", "le", "va", "vas", "anda", "andas", "estoy", "todo", "noche", "tarde",
}
# Tipos de cortesía: cada uno tiene su propia respuesta (no se repite la bienvenida larga)
_COMO_ESTAS = re.compile(r"\b(como (estas|esta|esta usted|te va|le va|andas|anda|vas|va todo)|que tal (estas|esta|todo))\b")
_MOMENTO = re.compile(r"\b(buenos dias|buen dia|buenas tardes|buenas noches)\b")
_DESPEDIDA = {"chao", "adios", "luego", "vemos", "pronto"}
_CONFIRMACION = {"ok", "okay", "oki", "vale", "listo", "perfecto", "genial", "excelente", "entendido", "acuerdo", "dale",
                 "bueno", "claro", "si", "super"}
# Preguntas sobre el propio asistente: se responde con lo que puede hacer y ejemplos concretos
_AYUDA = re.compile(r"^(hola |buenas |buenos dias |buenas tardes |buenas noches )?(que (puedes|podes|sabes|puede) "
                    r"hacer|en que (me )?(puedes|podes|puede) ayudar|que haces|que hace|ayuda|ayudame|help|"
                    r"quien eres|quien es usted|que eres|como funcionas|como funciona|como te uso|como lo uso|"
                    r"opciones|menu|comandos|instrucciones|para que sirves|que preguntas puedo hacer)"
                    r"( por favor)?$")


def _nombre_pila(docente: dict) -> str:
    """Primer nombre del docente («Roberto»)."""
    partes = [p for p in (docente.get("nombres") or "").split() if not p.endswith(".")]
    return partes[0] if partes else ""


def _trato_formal(docente: dict) -> str:
    """Trato respetuoso con título y primer apellido («Ing. Gómez»)."""
    partes = [p for p in (docente.get("nombres") or "").split() if not p.endswith(".")]
    apellido = partes[2] if len(partes) >= 4 else partes[-1] if len(partes) >= 2 else ""
    return f"Ing. {apellido}" if apellido else ""


def _trato(docente: dict) -> str:
    """Nombre corto del docente para el trato cordial: primer nombre y primer apellido."""
    partes = [p for p in (docente.get("nombres") or "").split() if not p.endswith(".")]
    if len(partes) >= 4:
        return f"{partes[0]} {partes[2]}"
    return " ".join(partes[:2])


def _ejemplos(docente: dict) -> List[str]:
    """2-3 consultas de ejemplo con datos reales del docente (su primera materia y un estudiante crítico)."""
    try:
        cursos = sync_service.cursos_del_docente(docente["email"])
    except Exception:  # noqa: BLE001 - sin sincronización: ejemplos genéricos
        cursos = []
    materia = re.sub(r",\s*paralelo \w$", "", _nombre_curso(cursos[0]["fullname"])) if cursos else "su curso"
    critico = next((e["nombres"] for c in cursos for e in sorted(c["estudiantes"], key=lambda x: x["nota_final"])
                    if e.get("nivel_riesgo") == "CRITICO"), None)
    if critico:
        partes = critico.split()
        critico = f"{partes[0]} {partes[2]}" if len(partes) >= 4 else critico
    return ["«¿Cómo van mis cursos?»", f"«¿Quién está en riesgo en {materia}?»",
            f"«Prepárame un plan de apoyo para {critico}»" if critico else "«Dame los reprobados»"]


def _variante(opciones: List[str], previas: int) -> str:
    """Rota las respuestas breves para no repetir la misma frase en la conversación."""
    return opciones[previas % len(opciones)]


def clasificar_cortesia(mensaje: str) -> Optional[str]:
    """ayuda | como_estas | momento | despedida | gracias | confirmacion | saludo, o None si es una consulta."""
    texto = " ".join(re.findall(r"[a-z0-9]+", _normalizar(mensaje)))
    if _AYUDA.match(texto):
        return "ayuda"
    palabras = texto.split()
    if not palabras or len(palabras) > 7 or any(p not in _VOCABULARIO_CORTESIA for p in palabras):
        return None
    if _COMO_ESTAS.search(texto):
        return "como_estas"
    if _DESPEDIDA & set(palabras):
        return "despedida"
    if "gracias" in palabras:
        return "gracias"
    if _MOMENTO.search(texto):
        return "momento"
    if _CONFIRMACION & set(palabras):
        return "confirmacion"
    return "saludo"


def respuesta_cortesia(mensaje: str, docente: dict, previas: Optional[Dict[str, int]] = None) -> Optional[str]:
    """
    Respuesta inmediata (sin herramientas ni LLM) a saludos, cortesías y preguntas sobre el asistente; cada tipo
    tiene su propia respuesta. `previas` cuenta las cortesías de ese tipo ya respondidas en la conversación
    (para no repetir la bienvenida larga ni la misma frase). None si el mensaje contiene una consulta real.
    """
    tipo = clasificar_cortesia(mensaje)
    if not tipo:
        return None
    previas = previas or {}
    n = previas.get(tipo, 0)
    pila, formal = _nombre_pila(docente), _trato_formal(docente)
    texto = " ".join(re.findall(r"[a-z0-9]+", _normalizar(mensaje)))
    ejemplos = "\n".join(f"- {e}" for e in _ejemplos(docente))

    if tipo == "ayuda":
        return (f"Soy CoraIA, su asistente académico de la FISEI{', ' + formal if formal else ''}. Reviso sus cursos de "
                "Moodle UTA, detecto a los estudiantes en riesgo y preparo planes de apoyo. Puede preguntarme, por "
                f"ejemplo:\n{ejemplos}")
    if tipo == "como_estas":
        momento = _MOMENTO.search(texto)
        inicio = (f"¡{momento.group(1).capitalize().replace('dias', 'días')}, {formal}! " if momento
                  else f"¡Hola, {pila}! " if re.search(r"\b(hola|holi|hey|saludos)\b", texto) else "")
        cuerpo = _variante([
            f"Muy bien, gracias por preguntar{'' if inicio else ', ' + formal}. Listo para ayudarle a revisar el "
            "rendimiento de sus cursos o preparar algún plan de apoyo. ¿Qué necesita consultar hoy?",
            "Todo en orden por aquí, gracias. ¿Revisamos cómo van sus cursos o algún estudiante en particular?",
        ], n)
        return inicio + cuerpo
    if tipo == "momento":
        saludo = _MOMENTO.search(texto).group(1).replace("dias", "días").replace("buen dia", "buen día").capitalize()
        return _variante([
            f"¡{saludo}, {formal}! ¿En qué puedo apoyarle hoy con sus cursos?",
            f"¡{saludo}, {formal}! Aquí estoy; dígame qué curso o estudiante desea revisar.",
        ], n)
    if tipo == "despedida":
        return _variante([f"¡Hasta pronto, {formal}! Que tenga una excelente jornada.",
                          "¡Hasta luego! Aquí estaré cuando necesite revisar sus cursos."], n)
    if tipo == "gracias":
        return _variante([f"Con gusto, {formal}. Si necesita algo más, solo pregúnteme.",
                          "¡A la orden! Cuando quiera revisamos otro curso o estudiante.",
                          f"Para eso estoy, {formal}. ¿Algo más en lo que pueda apoyarle?"], n)
    if tipo == "confirmacion":
        return _variante(["Perfecto. Cuando quiera, puedo revisar alertas, las notas de un estudiante o preparar un "
                          "refuerzo.", "Listo. Quedo atento a su próxima consulta."], n)
    # «hola», «qué tal»: presentación con ejemplos sólo la primera vez en la conversación
    if n:
        return _variante([f"¡Hola de nuevo, {pila}! ¿Qué desea revisar ahora?",
                          f"¡Aquí sigo, {pila}! ¿Con qué curso o estudiante continuamos?"], n - 1)
    return (f"¡Hola, {pila}! Soy CoraIA, el asistente académico de la FISEI. Puedo revisar sus cursos, detectar a los "
            f"estudiantes en riesgo y preparar planes de apoyo. Por ejemplo:\n{ejemplos}")


def ayuda_sin_intencion(docente: dict) -> str:
    """Aclaración en una frase, con opciones claras, cuando no se entiende la consulta."""
    nombre = _trato(docente)
    if idioma.IDIOMA.get() == "en":
        return (f"Could you be more specific{', ' + nombre if nombre else ''}? Would you like the **overall summary** "
                "of your courses, the **at-risk students** or a **student's grades**? Type, for example, «overall "
                "summary», «who is at risk» or the student's name.")
    return (f"No estoy seguro de qué necesita{', ' + nombre if nombre else ''}. ¿Quiere ver el **resumen general** "
            "de sus cursos, los **estudiantes en riesgo** o las **notas de un estudiante**? Escriba, por ejemplo, "
            "«resumen general», «quién está mal» o el nombre del estudiante.")


def _paralelo(c: Dict[str, Any]) -> Optional[str]:
    m = re.search(r"-\s*([a-z])$", _normalizar(c.get("fullname") or "")) or \
        re.search(r"-([a-z])$", _normalizar(c.get("shortname") or ""))
    return m.group(1) if m else None


# Siglas institucionales de las materias (sin importar mayúsculas ni tildes) -> sigla del código del curso
SIGLAS_MATERIAS = {"poo": "POO", "ed": "ED", "ma": "MA", "mcs": "MCS", "is1": "IS1", "is": "IS1", "isi": "IS1",
                   "bda": "BDA", "bd": "BDA", "dw": "DW"}


def _sigla_de(c: Dict[str, Any]) -> str:
    partes = [p for p in (c.get("shortname") or "").upper().split("-") if p and p != "SOF"]
    return partes[0] if partes else ""


def _curso_mencionado(texto: str, cursos: List[Dict[str, Any]]) -> Optional[int]:
    """Curso nombrado por su código (SOF-POO-A), sigla (POO, IS, BD...) o nombre de la materia, con su paralelo."""
    siglas = {SIGLAS_MATERIAS[w] for w in re.findall(r"[a-z0-9]+", texto) if w in SIGLAS_MATERIAS}
    candidatos = [c for c in cursos if _sigla_de(c) in siglas]
    for c in cursos:
        if c in candidatos:
            continue
        codigo = _normalizar(c["shortname"])
        partes = [p for p in codigo.split("-") if p and p != "sof"]
        abreviatura = partes[0] if partes else codigo
        if codigo in texto:
            return c["id"]
        palabras = [p for p in re.findall(r"[a-z]{5,}", _normalizar(c["fullname"] or ""))]
        if (re.search(rf"\b{re.escape(abreviatura)}\b", texto)
                or (palabras and sum(1 for p in palabras if p in texto) >= min(2, len(palabras)))):
            candidatos.append(c)
    if len(candidatos) > 1:
        paralelo = re.search(r"\bparalelo\s+([a-z])\b", texto)
        if paralelo:
            candidatos = [c for c in candidatos if _paralelo(c) == paralelo.group(1)] or candidatos
    return candidatos[0]["id"] if candidatos else None


def _palabras_de_cursos(cursos: List[Dict[str, Any]]) -> set:
    """Palabras de los nombres y siglas de las materias: nunca cuentan como parte del nombre de un estudiante."""
    palabras = set()
    for c in cursos:
        palabras |= set(re.findall(r"[a-z]{4,}", _normalizar(c.get("fullname") or "")))
        palabras |= {p for p in _normalizar(c.get("shortname") or "").split("-") if len(p) > 1}
    return palabras | {"paralelo", "materia", "materias", "curso", "cursos", "asignatura"}


def _estudiante_mencionado(texto: str, cursos: List[Dict[str, Any]]) -> Optional[str]:
    cedula = re.search(r"\b\d{10}\b", texto)
    if cedula:
        for c in cursos:
            for e in c["estudiantes"]:
                if e.get("cedula") == cedula.group(0):
                    return e["nombres"]
    codigo = re.search(r"\bu-?\d{2}\b", texto)
    if codigo:
        valor = codigo.group(0).upper()
        return valor if "-" in valor else f"U-{valor[1:]}"
    # Nombre completo (dos nombres y dos apellidos) o parcial: gana el estudiante con más palabras mencionadas
    # («Marco Paredes» es Marco Antonio Paredes Velasco, no Carlos Andrés Mendoza Paredes). Con una sola palabra
    # basta si ningún otro estudiante la comparte («Valeria», «Mendoza»); si la comparten, no se adivina.
    mejor, candidatos = _candidatos_por_nombre(texto, cursos)
    return candidatos[0] if mejor >= 1 and len(candidatos) == 1 else None


# Palabras frecuentes en las consultas que nunca se comparan (aproximadamente) con nombres de estudiantes
_PALABRAS_CONSULTA = {
    "nota", "notas", "curso", "cursos", "alumno", "alumnos", "estudiante", "estudiantes", "promedio", "dame",
    "como", "esta", "estan", "quien", "quienes", "cual", "cuales", "tiene", "tienen", "plan", "apoyo", "refuerzo",
    "materia", "materias", "alerta", "alertas", "riesgo", "resumen", "general", "unidad", "tarea", "tareas",
    "parcial", "actividad", "actividades", "calificaciones", "prepara", "preparame", "necesito", "quiero", "sobre",
    "todos", "todas", "favor", "para", "mis", "muestrame", "muestra", "revisa", "revisar", "ayuda", "ayudame",
}


def _palabra_mencionada(p: str, texto: str, palabras_texto: List[str]) -> bool:
    """Coincidencia exacta o con un error menor de escritura (sin tildes, una letra cambiada u omitida)."""
    if re.search(rf"\b{re.escape(p)}\b", texto):
        return True
    if len(p) < 5:
        return False
    return any(w[0] == p[0] and SequenceMatcher(None, p, w).ratio() >= 0.83 for w in palabras_texto)


def _candidatos_por_nombre(texto: str, cursos: List[Dict[str, Any]]) -> Tuple[int, List[str]]:
    """(mejor puntaje, estudiantes con ese puntaje) según las palabras de su nombre mencionadas en el texto."""
    de_cursos = _palabras_de_cursos(cursos)
    palabras_texto = [w for w in re.findall(r"[a-z]{4,}", texto) if w not in de_cursos and w not in _PALABRAS_CONSULTA]
    puntajes: Dict[str, int] = {}
    for c in cursos:
        for e in c["estudiantes"]:
            partes = [p for p in _normalizar(e["nombres"] or "").split() if len(p) > 3 and p not in de_cursos]
            puntajes[e["nombres"]] = sum(1 for p in partes if _palabra_mencionada(p, texto, palabras_texto))
    mejor = max(puntajes.values(), default=0)
    return mejor, ([n for n, p in puntajes.items() if p == mejor] if mejor else [])


def estudiantes_ambiguos(texto: str, cursos: List[Dict[str, Any]]) -> List[str]:
    """Estudiantes entre los que el mensaje no permite decidir («Carlos», «Paredes»); [] si no hay ambigüedad."""
    mejor, candidatos = _candidatos_por_nombre(texto, cursos)
    return candidatos if mejor >= 1 and len(candidatos) > 1 else []


def _contexto(mensaje: str, docente: dict, course_id: Optional[int]) -> Dict[str, Any]:
    """Curso explícito, alcance global, estudiante mencionado y curso efectivo de la consulta."""
    texto = _normalizar(mensaje)
    cursos = sync_service.cursos_del_docente(docente["email"])
    explicito = _curso_mencionado(texto, cursos)
    estudiante = _estudiante_mencionado(texto, cursos)
    global_ = bool(_GLOBAL.search(texto))
    if explicito:
        curso = explicito
    elif global_ or estudiante:
        curso = None  # transversal: todos los cursos del docente (o todos los del estudiante)
    else:
        curso = course_id
    return {"texto": texto, "curso": curso, "explicito": explicito, "estudiante": estudiante,
            "global": global_, "contexto": course_id,
            "criterio": criterio_nota(texto) or (None if estudiante else _criterio_informal(texto))}


def planificar_por_reglas(mensaje: str, docente: dict, course_id: Optional[int] = None) -> List[Tuple[str, Dict]]:
    """Planificador determinista de respaldo: intención por palabras clave + curso/estudiante mencionados."""
    ctx = _contexto(mensaje, docente, course_id)
    texto, curso, estudiante = ctx["texto"], ctx["curso"], ctx["estudiante"]
    base = {"course_id": curso} if curso else {}
    plan: List[Tuple[str, Dict]] = []

    if _PIDE_PDF.search(texto):
        # «Dame el pdf»: del estudiante nombrado o, si no se nombra, del último consultado en la conversación
        previo = None if estudiante else estudiante_en_contexto(docente)
        quien = estudiante or (previo or {}).get("nombres")
        if not quien:
            return []
        curso_pdf = ctx["explicito"] or (previo or {}).get("course_id") or (None if estudiante else course_id)
        return [("generar_guia_pdf", {"student_query": quien, **({"course_id": curso_pdf} if curso_pdf else {})})]

    if ctx["criterio"] and not (_REFUERZO.search(texto) and estudiante):
        # Umbral explícito: sólo las matrículas que lo cumplen (todas las materias salvo que se nombre una).
        curso_umbral = ctx["explicito"] or (None if ctx["global"] else course_id)
        return [("obtener_calificaciones", {**({"course_id": curso_umbral} if curso_umbral else {}),
                                            **ctx["criterio"]})]
    if _PERFIL.search(texto):
        return [("perfil_docente", {})]
    extremo = extremo_pedido(texto)
    if extremo and not estudiante:
        # «El estudiante con la peor nota de POO»: se destaca a ese único estudiante (no el bloque de alertas)
        curso_extremo = ctx["explicito"] or (None if ctx["global"] else course_id)
        return [("obtener_calificaciones", {**({"course_id": curso_extremo} if curso_extremo else {}),
                                            "extremo": extremo})]
    if ctx["explicito"] and not estudiante and (_CONTEO.search(texto) or _pide_lista(texto)):
        # Nómina de UNA materia: «¿cuántos estudiantes tengo en POO?» (sólo la cifra) o «lista completa de ED»
        conteo = bool(_CONTEO.search(texto)) and not _pide_lista(texto)
        return [("listar_estudiantes", {"course_id": ctx["explicito"], **({"solo_conteo": True} if conteo else {})})]
    if _PANORAMA.search(texto) and not estudiante:
        # «¿Cómo van mis cursos?», «resumen general»: panorama de una materia nombrada o de todas
        return [("generar_resumen", {"course_id": ctx["explicito"]} if ctx["explicito"] else {})]
    if _EN_PROBLEMAS.search(texto) and not estudiante and not _REFUERZO.search(texto):
        return [("identificar_alertas", base)]
    if _REFUERZO.search(texto) and estudiante:
        # El curso activo se usa sólo si el estudiante está matriculado en él (lo resuelve la herramienta).
        curso_refuerzo = ctx["explicito"] or ctx["contexto"]
        return [("proponer_refuerzo", {"student_query": estudiante,
                                       **({"course_id": curso_refuerzo} if curso_refuerzo else {})})]
    if _CURSOS.search(texto):
        plan.append(("listar_cursos_autorizados", {}))
    if _ACTIVIDADES.search(texto):
        plan.append(("analizar_actividades", base))
    if estudiante or re.search(r"\b(nota|notas|calificacion|calificaciones|promedio de|rendimiento de)\b", texto):
        plan.append(("obtener_calificaciones", {**base, **({"estudiante": estudiante} if estudiante else {})}))
    if re.search(r"\b(alerta|alertas|riesgo|critic\w*|atencion|ayuda|reprob\w*|descenso|r1|r2|refuerzo|mal)\b", texto):
        regla = "R1" if re.search(r"\b(r1|critic\w*)\b", texto) and "r2" not in texto else (
            "R2" if re.search(r"\b(r2|descenso|baja)\b", texto) else None)
        plan.append(("identificar_alertas", {**base, **({"regla": regla} if regla else {})}))
    resumen = r"\b(resumen|informe|reporte|panorama|estado del curso|situacion)\b"
    if re.search(resumen, texto) or (not estudiante and re.search(r"\b(como va|como esta|como van)\b", texto)):
        plan.append(("generar_resumen", base))
    # Sin intención clara no se lanza ningún informe: conversar() pide precisar la consulta.
    return plan[:MAX_HERRAMIENTAS_POR_MENSAJE]


def _validar_plan(llamadas: Any, docente: dict) -> List[Tuple[str, Dict]]:
    """Acepta sólo herramientas conocidas, parámetros esperados y cursos del docente."""
    if not isinstance(llamadas, list):
        return []
    propios = {c["id"] for c in sync_service.cursos_del_docente(docente["email"])}
    plan = []
    for llamada in llamadas[:MAX_HERRAMIENTAS_POR_MENSAJE]:
        nombre = (llamada or {}).get("herramienta")
        params = (llamada or {}).get("parametros") or {}
        if nombre not in EJECUTORES or not isinstance(params, dict):
            return []
        params = {k: v for k, v in params.items() if k in _PARAMETROS_VALIDOS[nombre] and v not in (None, "")}
        if "course_id" in params:
            try:
                params["course_id"] = int(params["course_id"])
            except (TypeError, ValueError):
                return []
            if params["course_id"] not in propios:
                return []
        plan.append((nombre, params))
    return plan


def _resolver_entidades(plan: List[Tuple[str, Dict]], mensaje: str, docente: dict,
                        course_id: Optional[int]) -> List[Tuple[str, Dict]]:
    """
    El LLM decide QUÉ herramientas usar; el curso, el alcance y el estudiante que el mensaje menciona se
    resuelven de forma determinista y prevalecen sobre lo que proponga el modelo (evita, p. ej., que
    «Estructura de Datos» termine consultando otro curso o que una pregunta transversal se limite a uno).
    """
    ctx = _contexto(mensaje, docente, course_id)
    cursos = sync_service.cursos_del_docente(docente["email"])
    resuelto = []
    for nombre, params in plan:
        params = dict(params)
        if nombre == "proponer_refuerzo":
            # Sólo si el docente pide un refuerzo y nombra a un estudiante real (el modelo pequeño a veces
            # propone esta herramienta con el mensaje completo como student_query).
            estudiante = ctx["estudiante"]
            if not estudiante or not _REFUERZO.search(ctx["texto"]):
                continue
            params = {"student_query": estudiante}
            if ctx["explicito"] or ctx["contexto"]:
                params["course_id"] = ctx["explicito"] or ctx["contexto"]
        elif nombre == "generar_guia_pdf":
            # Sólo si el mensaje pide el PDF y nombra a un estudiante real (el contexto lo resuelven las reglas)
            if not ctx["estudiante"] or not _PIDE_PDF.search(ctx["texto"]):
                continue
            params = {"student_query": ctx["estudiante"], **({"course_id": ctx["explicito"]} if ctx["explicito"] else {})}
        elif nombre != "listar_cursos_autorizados":
            if ctx["curso"]:
                params["course_id"] = ctx["curso"]
            elif ctx["global"] or ctx["estudiante"]:
                params.pop("course_id", None)
            if nombre == "obtener_calificaciones":
                if ctx["estudiante"]:
                    params["estudiante"] = ctx["estudiante"]
                elif params.get("estudiante") and not _es_estudiante(str(params["estudiante"]), cursos):
                    # El modelo pequeño a veces pasa la materia («Programación orientada a objetos») como estudiante
                    params.pop("estudiante")
                for clave in ("operador", "umbral", "umbral_max"):
                    params.pop(clave, None)
                if ctx["criterio"]:
                    params.update(ctx["criterio"])
        elif ctx["explicito"] and not _CURSOS.search(ctx["texto"]):
            continue  # el docente preguntó por una materia concreta, no por el listado de sus cursos
        resuelto.append((nombre, params))
    return resuelto


def _es_estudiante(valor: str, cursos: List[Dict[str, Any]]) -> bool:
    """True si el valor nombra a un estudiante real del docente y no a una de sus materias."""
    filtro = _normalizar(valor)
    if not filtro or _curso_mencionado(filtro, cursos):
        return False
    return any(_coincide(e, filtro) for c in cursos for e in c["estudiantes"])


async def planificar(mensaje: str, docente: dict, course_id: Optional[int]) -> Tuple[List[Tuple[str, Dict]], str]:
    """Plan del LLM (vía microservicio del agente) validado; si falla, planificador por reglas."""
    texto = _normalizar(mensaje)
    if criterio_nota(texto):
        return planificar_por_reglas(mensaje, docente, course_id), "reglas_deterministas"
    # Mensajes simples: respuesta inmediata sin esperar a Ollama (con intención clara se ejecutan las reglas; sin
    # ella, conversar() pide precisar al instante). Las frases largas sin intención directa pasan por el LLM.
    reglas = planificar_por_reglas(mensaje, docente, course_id)
    if len(re.findall(r"[a-z0-9]+", texto)) <= MAX_PALABRAS_RAPIDAS or (reglas and _intencion_directa(texto)):
        return reglas, "reglas_deterministas"
    cursos = [{"id": c["id"], "shortname": c["shortname"], "fullname": c["fullname"]}
              for c in sync_service.cursos_del_docente(docente["email"])]
    try:
        async with httpx.AsyncClient(timeout=AGENT_CHAT_TIMEOUT_SECONDS) as client:
            resp = await client.post(f"{AGENT_HOST}/api/v1/chat/plan", json={
                "mensaje": mensaje, "cursos": cursos, "course_id": course_id,
                "herramientas": [{"nombre": n, **d} for n, d in CATALOGO.items()],
            })
        if resp.status_code == 200:
            data = resp.json()
            plan = _resolver_entidades(_validar_plan(data.get("llamadas"), docente), mensaje, docente, course_id)
            if plan:
                reglas = planificar_por_reglas(mensaje, docente, course_id)
                if reglas == [("listar_cursos_autorizados", {})]:
                    # Pregunta sólo de conteos/listado: respuesta acotada, sin anexar alertas ni informes.
                    usa_listado = any(n == "listar_cursos_autorizados" for n, _ in plan)
                    return reglas, data.get("fuente", "ollama_slm") if usa_listado else "reglas_deterministas"
                if any(n == "proponer_refuerzo" for n, _ in reglas):
                    # Pedido explícito de refuerzo: la propuesta es la respuesta; no se diluye con otras consultas.
                    plan = [p for p in plan if p[0] == "proponer_refuerzo"] or reglas
                    return plan[:1], data.get("fuente", "ollama_slm") + ("" if plan[0] in reglas else "+reglas")
                # El modelo pequeño puede omitir la herramienta que la pregunta pide explícitamente:
                # se complementa con las del planificador por reglas (sin duplicar herramientas).
                usadas = {n for n, _ in plan}
                extra = [(n, p) for n, p in reglas if n not in usadas]
                fuente = data.get("fuente", "ollama_slm") + ("+reglas" if extra else "")
                return (plan + extra)[:MAX_HERRAMIENTAS_POR_MENSAJE], fuente
    except Exception as ex:  # agente caído o lento: respaldo determinista
        logger.info("Planificador del agente no disponible (%s); se usa el de reglas.", ex.__class__.__name__)
    return planificar_por_reglas(mensaje, docente, course_id), "reglas_deterministas"


# =============================================================================== Redacción (sólo con datos)
Seccion = Tuple[str, str, List[str]]  # (título, frase clave para el resumen ejecutivo, líneas Markdown)


def _seccion_cursos(r: Dict[str, Any]) -> Seccion:
    if not r["cursos"]:
        return ("Cursos asignados", "No tiene cursos sincronizados.",
                ["Pulse **Sincronizar** para importar sus cursos desde Moodle UTA."])
    t = r["totales"]
    clave = (f"Tiene **{t['cursos']} cursos** asignados con **{t['estudiantes_unicos']} estudiantes únicos** "
             f"({t['matriculas']} matrículas en total).")
    # Lista compacta: sólo cifras (alertas y recomendaciones se reservan para el «resumen general»).
    lineas = [f"- **{_nombre_curso(c['fullname'])}**: {c['total_estudiantes']} estudiantes"
              for c in r["cursos"]]
    return "Cursos asignados", clave, lineas


def _alcance(r: Dict[str, Any]) -> str:
    cursos = r.get("cursos_consultados") or []
    if len(cursos) == 1:
        return f"en {_nombre_curso(cursos[0]['fullname'])}"
    return f"en sus {len(cursos)} cursos"


def _seccion_calificaciones_criterio(r: Dict[str, Any]) -> Seccion:
    filas, criterio = r["calificaciones"], texto_criterio(r["criterio"])
    if not filas:
        return ("Calificaciones", f"Ninguna matrícula tiene **{criterio}** {_alcance(r)}.", [])
    clave = f"Encontré **{idioma.plural(len(filas), 'matrícula', 'matrículas')}** con **{criterio}** {_alcance(r)}:"
    una_materia = len(r.get("cursos_consultados") or []) == 1
    lineas = [f"- **{f['nombres']}**" + ("" if una_materia else f" · {_nombre_curso(f['curso_nombre'])}")
              + f": **{f['nota_final']:.2f}/10** ({NIVEL_TEXTO.get(f['nivel_riesgo'], f['nivel_riesgo'])})"
              for f in filas]
    return f"Calificaciones con {criterio}", clave, lineas


def _curso_titulo(fullname: str) -> str:
    """'Programación orientada a objetos — Paralelo A'."""
    return _nombre_curso(fullname).replace(", paralelo", " — Paralelo")


def _seccion_extremo(r: Dict[str, Any]) -> Seccion:
    """Destaca primero al único estudiante con la menor / mayor nota; debajo, otros en riesgo (o los que siguen)."""
    filas, peor = r["calificaciones"], r["extremo"] == "peor"
    cursos = r.get("cursos_consultados") or []
    una_materia = len(cursos) == 1
    alcance = f"En **{_curso_titulo(cursos[0]['fullname'])}**" if una_materia else f"En sus {len(cursos)} cursos"
    if not filas:
        return ("Calificaciones", f"{alcance} aún no hay calificaciones sincronizadas.", [])
    nivel = lambda f: NIVEL_TEXTO.get(f["nivel_riesgo"], f["nivel_riesgo"])  # noqa: E731
    primero = filas[0]
    empatados = [f for f in filas if f["nota_final"] == primero["nota_final"]]
    donde = lambda f: "" if una_materia else f" en {_curso_titulo(f['curso_nombre'])}"  # noqa: E731
    adjetivo = "menor" if peor else "mayor"
    if len(empatados) == 1:
        clave = (f"{alcance}, el estudiante con la **{adjetivo} calificación** es **{primero['nombres']}**"
                 f"{donde(primero)}, con **{primero['nota_final']:.2f}/10** ({nivel(primero)}).")
    else:
        clave = (f"{alcance}, **{len(empatados)} estudiantes** comparten la {adjetivo} calificación "
                 f"(**{primero['nota_final']:.2f}/10**, {nivel(primero)}): "
                 + _lista_y([f"**{f['nombres']}**{donde(f)}" for f in empatados]) + ".")
    restantes = filas[len(empatados):]
    if peor:
        otros = [f for f in restantes if f["nivel_riesgo"] != "ACEPTABLE"][:5]
        titulo_otros = "También requieren seguimiento:"
    else:
        otros = restantes[:2]
        titulo_otros = "Le siguen:"
    lineas = ([titulo_otros] + [f"- {f['nombres']}{donde(f)}: **{f['nota_final']:.2f}/10** ({nivel(f)})"
                                for f in otros]) if otros else []
    titulo = f"{'Menor' if peor else 'Mayor'} calificación"
    return titulo, clave, lineas


def _lista_y(items: List[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


def _seccion_calificaciones(r: Dict[str, Any]) -> Seccion:
    filas = r["calificaciones"]
    if r.get("extremo"):
        return _seccion_extremo(r)
    if r.get("criterio"):
        return _seccion_calificaciones_criterio(r)
    if r.get("estudiante"):
        # Ficha individual: nombre y cédula (sin el código interno U-xx), una cabecera por materia, una línea
        # de notas y las incidencias reales; las pendientes de calificar se resumen en un solo conteo.
        nombre = filas[0]["nombres"]
        cedula = f" (C.I. {filas[0]['cedula']})" if filas[0].get("cedula") else ""
        n = len(filas)
        criticos = sum(1 for f in filas if f["nivel_riesgo"] == "CRITICO")
        promedio = sum(f["nota_final"] for f in filas) / n
        if n == 1:
            f0 = filas[0]
            clave = (f"**{nombre}**{cedula} · Tiene **{f0['nota_final']:.2f}/10** "
                     f"({NIVEL_TEXTO.get(f0['nivel_riesgo'], f0['nivel_riesgo'])}) en "
                     f"**{_curso_titulo(f0['curso_nombre'])}**.")
        else:
            estado = (f"**estado crítico en sus {n} materias**" if criticos == n
                      else "ninguna materia en estado crítico" if criticos == 0
                      else f"**estado crítico en {criticos} de sus {n} materias**")
            clave = (f"**{nombre}**{cedula} · Cursa **{n} materias** con promedio general de "
                     f"**{promedio:.2f}/10** ({estado}).")
        lineas = []
        for f in sorted(filas, key=lambda x: x["nota_final"]):
            nivel = NIVEL_TEXTO.get(f["nivel_riesgo"], f["nivel_riesgo"]).capitalize()
            lineas.append(f"- **{_curso_titulo(f['curso_nombre'])}**")
            lineas.append(f"  - Promedio: **{f['nota_final']:.2f}/10 ({nivel})** · Exámenes: {_f(f['acd'])} | "
                          f"Tareas: {_f(f['tareas'])} | APE: {_f(f['pae'])} · Tendencia: "
                          f"{TENDENCIA_TEXTO.get(f['tendencia'], (f['tendencia'] or '—').lower())}")
            if f["incidencias"]:
                lineas.append("  - Incidencias: " + idioma.resumen_incidencias(
                    f["incidencias"], _INCIDENCIA_TEXTO,
                    ("actividad pendiente de calificación", "actividades pendientes de calificación")))
        return f"Calificaciones de {nombre}", clave, lineas

    por_curso: Dict[str, List[Dict[str, Any]]] = {}
    for f in filas:
        por_curso.setdefault(f["curso"], []).append(f)
    criticos = [f for f in filas if f["nivel_riesgo"] == "CRITICO"]
    en_riesgo = sum(1 for f in filas if f["nivel_riesgo"] == "EN_RIESGO")
    if len(por_curso) == 1:
        # Una sola materia: el curso ya va en la frase clave; la lista es directamente la de sus estudiantes
        curso_unico = _curso_titulo(filas[0]["curso_nombre"])
        aprobados = sum(1 for f in filas if f["nota_final"] >= UMBRAL_APROBACION)
        clave = (f"En **{curso_unico}** revisé **{len(filas)} calificaciones** ({aprobados} aprobados): "
                 f"**{len(criticos)} en nivel crítico** y {en_riesgo} en riesgo.")
        seguimiento = sorted((f for f in filas if f["nivel_riesgo"] != "ACEPTABLE"), key=lambda x: x["nota_final"])
        lineas = [f"- {f['nombres']}: **{f['nota_final']:.2f}/10** ({NIVEL_TEXTO.get(f['nivel_riesgo'])})"
                  + (f" · {idioma.plural(len(f['incidencias']), 'incidencia', 'incidencias')}" if f["incidencias"] else "")
                  for f in seguimiento[:6]]
        return "Calificaciones", clave, lineas or ["- Todos los estudiantes están aprobando."]
    else:
        clave = (f"Revisé **{len(filas)} calificaciones** en {len(por_curso)} cursos: **{len(criticos)} en nivel "
                 f"crítico** y {en_riesgo} en riesgo.")
    lineas = []
    for curso, lista in por_curso.items():
        lista.sort(key=lambda x: x["nota_final"])
        aprobados = sum(1 for f in lista if f["nota_final"] >= UMBRAL_APROBACION)
        lineas.append(f"- **{curso}** ({len(lista)} estudiantes, {aprobados} aprobados)")
        seguimiento = [f for f in lista if f["nivel_riesgo"] != "ACEPTABLE"]
        for f in seguimiento[:6]:
            lineas.append(f"  - {f['nombres']}: **{f['nota_final']:.2f}/10** ({NIVEL_TEXTO.get(f['nivel_riesgo'])})"
                          + (f" · {idioma.plural(len(f['incidencias']), 'incidencia', 'incidencias')}"
                             if f["incidencias"] else ""))
        if not seguimiento:
            lineas.append("  - Todos los estudiantes están aprobando.")
    return "Calificaciones", clave, lineas


def _seccion_alertas(r: Dict[str, Any]) -> Seccion:
    alertas = sorted(r["alertas"], key=lambda a: (a.get("nota_final") is None, a.get("nota_final") or 0))
    if not alertas:
        return "Alertas tempranas", "No hay alertas activas para el criterio consultado.", []
    abiertas = sum(1 for a in alertas if a["estado"] == "ABIERTA")
    clave = (f"Hay **{idioma.plural(len(alertas), 'alerta activa', 'alertas activas')}**; "
             + (f"{abiertas} sigue abierta y requiere" if abiertas == 1 else f"{abiertas} siguen abiertas y requieren")
             + " atención prioritaria.")
    lineas = [f"- **{a['nombres']}** ({a['curso']}) · "
              f"{'Nota crítica' if a['regla'].startswith('R1') else 'Descenso sostenido'} · nota **{_f(a.get('nota_final'))}/10**"
              + (f" · pendiente {a['pendiente']:+.2f}" if a.get("pendiente") is not None else "")
              + f" · {ESTADO_ALERTA_TEXTO.get(a['estado'], a['estado'].lower())}" for a in alertas]
    if abiertas:
        lineas.append("\n**Sugerencia:** atienda primero las alertas abiertas desde el *Centro de alertas* o pídame "
                      "que prepare un refuerzo para un estudiante concreto.")
    return "Alertas tempranas", clave, lineas


def _seccion_resumen(r: Dict[str, Any]) -> List[Seccion]:
    secciones = []
    for s in r["resumenes"]:
        m, d = s["metricas"], s["distribucion_estados"]
        clave = (f"**{s['curso']}** tiene promedio **{m['promedio']:.2f}/10** y **{m['porcentaje_aceptables']:.1f} %** "
                 f"de aprobación.")
        lineas = [
            f"- **Promedio:** {m['promedio']:.2f}/10 (mediana {m['mediana']:.2f}; rango {m['nota_minima']:.2f}–{m['nota_maxima']:.2f})",
            f"- **Niveles:** {idioma.plural(m['criticos'], 'crítico', 'críticos')}, {m['en_riesgo']} en riesgo y "
            f"{idioma.plural(m['aceptables'], 'aceptable', 'aceptables')} de {m['total_estudiantes']}",
            f"- **Entregas:** {d['cero']} con nota 0, {d['sin_entrega']} sin entrega y "
            f"{idioma.plural(d['pendiente'], 'pendiente', 'pendientes')} de "
            f"{idioma.plural(d['total_registros'], 'registro', 'registros')}",
        ]
        if s["hallazgos"][1:]:
            lineas.append("\n**Hallazgos clave**")
            lineas += [f"- {h}" for h in s["hallazgos"][1:4]]
        if s["recomendaciones"]:
            lineas.append("\n**Recomendaciones**")
            lineas += [f"- {rec}" for rec in s["recomendaciones"][:3]]
        secciones.append((f"Resumen de {s['curso']}", clave, lineas))
    return secciones or [("Resumen", "No hay cursos para resumir.", [])]


def _seccion_actividades(r: Dict[str, Any]) -> Seccion:
    acts = [a for a in r["actividades"] if a["promedio"] is not None]
    if not acts:
        return "Rendimiento por actividad", "No hay actividades calificadas en el alcance consultado.", []
    peor = acts[0]
    clave = (f"La actividad con menor rendimiento es **{peor['actividad']} · {peor['nombre']}** de {peor['curso']} "
             f"(promedio **{peor['promedio']:.2f}/10**).")
    lineas = ["Actividades con menor promedio (de menor a mayor):"]
    for a in acts[:5]:
        extras = [f"{a['bajo_aprobacion']} de {a['calificaciones']} bajo 7.00"]
        if a["ceros"]:
            extras.append(f"{a['ceros']} con nota 0")
        if a["sin_entrega"]:
            extras.append(f"{a['sin_entrega']} sin entrega")
        if a["pendientes"]:
            extras.append(idioma.plural(a["pendientes"], "pendiente", "pendientes"))
        lineas.append(f"- **{a['curso']} · {a['actividad']}** {a['nombre']}: **{a['promedio']:.2f}/10** · " + ", ".join(extras))
    lineas.append("\n**Sugerencia:** revise el enunciado y la retroalimentación de estas actividades y considere "
                  "una sesión de refuerzo grupal sobre esos temas.")
    return "Rendimiento por actividad", clave, lineas


def _seccion_refuerzo(r: Dict[str, Any]) -> Seccion:
    p, ev, est = r["propuesta"], r["evidencia"], r["estudiante"]
    clave = (f"Preparé una propuesta de refuerzo para **{est['nombres']}** en **{r['curso']}**, donde su nota es "
             f"**{ev['nota_final']:.2f}/10**.")
    lineas = ["**Falencias detectadas**"]
    if ev["unidad_critica"]:
        lineas.append(f"- Unidad más baja: **{_unidad(ev['unidad_critica'])}** ({_f(ev['promedio_unidad_critica'])}/10)")
    if ev["componente_debil"]:
        lineas.append(f"- Componente más débil: **{NOMBRE_COMPONENTE[ev['componente_debil']]}** "
                      f"(peso {PESO_COMPONENTE[ev['componente_debil']]} %): {_f(ev['promedio_componente_debil'])}/10")
    if ev["incidencias"]:
        lineas.append("- Incidencias: " + ", ".join(f"{i['actividad']} ({_INCIDENCIA_TEXTO[i['tipo']]})" for i in ev["incidencias"]))
    lineas += ["", f"**Título:** {p['titulo']}", "", f"**Objetivo:** {p['objetivo']}", "", "**Descripción de la tarea**"]
    lineas += [f"{i}. {paso}" for i, paso in enumerate(p["pasos"], 1)]
    lineas += ["", "**Criterios de evaluación**"]
    lineas += [f"- {c['criterio']} — {c['peso']} %" for c in p["criterios"]]
    lineas += ["", f"**Plazo sugerido:** {p['plazo_dias']} días."]
    if r["otros_cursos"]:
        lineas.append("\nOtros cursos del estudiante: " + ", ".join(
            f"{o['curso']} ({o['nota_final']:.2f}/10)" for o in r["otros_cursos"]) + ".")
    if r["alerta"] and r["alerta"]["estado"] in ("ABIERTA", "ATENDIDA"):
        lineas.append(f"\nPuede aplicarla desde el **Centro de alertas** (alerta #{r['alerta']['id']}) para revisarla y "
                      "publicarla en Moodle.")
    elif r["alerta"]:
        lineas.append("\nEl estudiante ya tiene un refuerzo publicado para esta alerta en Moodle.")
    else:
        lineas.append("\nEl estudiante no tiene una alerta activa en este curso; la propuesta queda como referencia.")
    lineas.append("\nSi desea la **guía oficial en PDF** para el estudiante, escriba «dame el pdf».")
    return "Propuesta de refuerzo", clave, lineas


def _seccion_nomina(r: Dict[str, Any]) -> Seccion:
    curso = _nombre_curso(r["curso"]["fullname"]).replace(", paralelo", " — Paralelo")
    if r["solo_conteo"]:
        return ("Estudiantes", f"En **{curso}** tiene **{r['total']} estudiantes** matriculados.", [])
    lineas = [f"{i}. **{e['nombres']}** · {e.get('email') or 'sin correo'} · nota actual **{e['nota_final']:.2f}/10** "
              f"({NIVEL_TEXTO.get(e['nivel_riesgo'], e['nivel_riesgo'])})" for i, e in enumerate(r["estudiantes"], 1)]
    return (f"Estudiantes de {curso}", f"Estudiantes matriculados en **{curso}** ({r['total']}):", lineas)


def _seccion_perfil(r: Dict[str, Any]) -> Seccion:
    cedula = f", C.I. {r['cedula']}" if r.get("cedula") else ""
    n = len(r["cursos"])
    clave = (f"Usted es **{r['nombres']}** ({r['email']}{cedula}), docente de la FISEI. Tiene **{n} "
             f"{'curso asignado' if n == 1 else 'cursos asignados'}** en el período Julio a Diciembre 2026:")
    lineas = [f"- **{_nombre_curso(c['fullname']).replace(', paralelo', ' — Paralelo')}**: "
              f"{c['total_estudiantes']} estudiantes" for c in r["cursos"]]
    return "Su perfil", clave, lineas


def _seccion_guia_pdf(r: Dict[str, Any]) -> Seccion:
    est = r["estudiante"]
    curso = _nombre_curso(r["curso_nombre"]).replace(", paralelo", " — Paralelo")
    clave = (f"Listo: generé la **guía oficial de refuerzo UTA - FISEI** para **{est['nombres']}** en **{curso}** "
             f"({r['unidad']}).")
    return "Guía de refuerzo en PDF", clave, [
        "Ábrala o descárguela con el botón **Descargar guía PDF** de este mensaje. Incluye el tema, el objetivo, "
        "las instrucciones, el material de apoyo, un ejemplo resuelto y las actividades por desarrollar."]


def _secciones(nombre: str, r: Dict[str, Any]) -> List[Seccion]:
    if "error" in r:
        return [("Aviso", f"No pude completar una de las consultas: {r['error']}", [])]
    if nombre == "listar_cursos_autorizados":
        return [_seccion_cursos(r)]
    if nombre == "obtener_calificaciones":
        return [_seccion_calificaciones(r)]
    if nombre == "identificar_alertas":
        return [_seccion_alertas(r)]
    if nombre == "generar_resumen":
        return _seccion_resumen(r)
    if nombre == "analizar_actividades":
        return [_seccion_actividades(r)]
    if nombre == "proponer_refuerzo":
        return [_seccion_refuerzo(r)]
    if nombre == "listar_estudiantes":
        return [_seccion_nomina(r)]
    if nombre == "perfil_docente":
        return [_seccion_perfil(r)]
    if nombre == "generar_guia_pdf":
        return [_seccion_guia_pdf(r)]
    return []


def redactar(usadas: List[Dict[str, Any]]) -> str:
    """Respuesta en Markdown: resumen ejecutivo + una sección por resultado (sólo datos de las herramientas)."""
    en = idioma.IDIOMA.get() == "en"
    secciones = [s for u in usadas
                 for s in (idioma.secciones_en if en else _secciones)(u["herramienta"], u["resultado"])]
    if not secciones:
        return idioma.t("No encontré información para responder. Pruebe a sincronizar con Moodle UTA.",
                        "I found no information to answer. Try synchronizing with Moodle UTA.")
    if len(secciones) == 1:
        titulo, clave, lineas = secciones[0]
        return "\n".join([clave, ""] + lineas).strip()
    partes = [idioma.t("**Resumen ejecutivo**", "**Executive summary**")] + [f"- {clave}" for _, clave, _ in secciones]
    for titulo, _, lineas in secciones:
        if lineas:
            partes += ["", f"### {titulo}"] + lineas
    return "\n".join(partes).strip()


def _respuesta_sin_herramientas(texto: str, fuente: str, docente: dict, inicio: float,
                                extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    repositories.insert_log(
        "AGENTE_CHAT", "EXITO", f"Mensaje del docente respondido sin herramientas ({fuente}).",
        {"docente": docente["email"], "herramientas": [], "plan": fuente, **(extra or {})},
        int((time.time() - inicio) * 1000),
    )
    return {"respuesta": texto, "formato": "markdown", "herramientas": [], "plan_fuente": fuente,
            "redaccion": "determinista_sin_herramientas", "adjuntos": [], "idioma": idioma.IDIOMA.get(),
            "duracion_ms": int((time.time() - inicio) * 1000)}


_FUENTE_HERRAMIENTA = {
    "identificar_alertas": "Alertas tempranas registradas en MoodleUTADB",
    "generar_guia_pdf": "Guía PDF generada con las notas sincronizadas desde Moodle UTA",
    "perfil_docente": "Perfil del docente y cursos sincronizados desde Moodle UTA",
}


def trazabilidad(nombre: str, params: Dict[str, Any], resultado: Dict[str, Any], docente: dict) -> Dict[str, Any]:
    """
    RF-09 / RF-12: herramienta invocada, parámetros validados (curso por su código, estudiante, docente_id; nunca
    tokens ni contraseñas), estado y resultado, y la fuente de los datos con la fecha de la última sincronización.
    """
    from app.services.reporte_service import _fecha_hora
    cursos = {c["id"]: c["shortname"] for c in sync_service.cursos_del_docente(docente["email"])}
    validados: Dict[str, Any] = {}
    for clave, valor in params.items():
        if clave == "course_id":
            validados["curso"] = cursos.get(int(valor), valor)
        elif clave in ("estudiante", "student_query"):
            validados["estudiante"] = valor
        else:
            validados[clave] = valor
    if "curso" not in validados and isinstance(resultado.get("curso"), str):
        validados["curso"] = resultado["curso"]          # curso que resolvió la herramienta (plan de apoyo, guía)
    elif "curso" not in validados and nombre not in ("perfil_docente", "listar_cursos_autorizados"):
        validados["curso"] = "todos los cursos del docente"
    validados["docente_id"] = docente.get("id")
    error = resultado.get("error")
    fuente = _FUENTE_HERRAMIENTA.get(nombre, "Sincronizado desde Moodle UTA")
    ultima = sync_service.SYNC_STATE.get("ultima_sincronizacion")
    return {
        "herramienta": nombre,
        "parametros_validados": validados,
        "estado": "ERROR" if error else "OK",
        "resultado": error or idioma.plural(int(resultado.get("filas") or 0), "registro", "registros"),
        "fuente": f"{fuente} · {_fecha_hora(ultima)}" if ultima else fuente,
    }


def _respuesta_dominio(docente: dict, inicio: float) -> Dict[str, Any]:
    return _respuesta_sin_herramientas(idioma.mensaje_dominio(), "fuera_de_dominio", docente, inicio)


async def conversar(mensaje: str, docente: dict, course_id: Optional[int] = None) -> Dict[str, Any]:
    """Atiende un mensaje del docente en español o en inglés (CoraIA responde en el mismo idioma)."""
    lengua = idioma.detectar_idioma(mensaje)
    marca = idioma.IDIOMA.set(lengua)
    try:
        return await _conversar(mensaje, docente, course_id, lengua)
    finally:
        idioma.IDIOMA.reset(marca)


async def _conversar(mensaje: str, docente: dict, course_id: Optional[int], lengua: str) -> Dict[str, Any]:
    inicio = time.time()
    t = idioma.t
    if lengua == "en":
        cortesia = idioma.cortesia_en(mensaje, docente)
        if cortesia:
            return _respuesta_sin_herramientas(cortesia, "cortesia", docente, inicio, {"cortesia": "en"})
    else:
        tipo = clasificar_cortesia(mensaje)
        if tipo:  # saludo o cortesía: sin herramientas ni LLM, sin repetir la misma respuesta en la conversación
            previas: Dict[str, int] = {}
            for log in repositories.chats_recientes(docente["email"]):
                previo = (log.get("detalle") or {}).get("cortesia")
                if previo:
                    previas[previo] = previas.get(previo, 0) + 1
            texto = respuesta_cortesia(mensaje, docente, previas)
            return _respuesta_sin_herramientas(texto, "cortesia", docente, inicio, {"cortesia": tipo})
    if idioma.fuera_de_dominio(mensaje):
        # «2 + 2», «capital de España», chistes...: CoraIA delimita su alcance (no resuelve temas externos)
        return _respuesta_dominio(docente, inicio)
    # Una consulta en inglés se lleva a las mismas intenciones (en español) que entiende el planificador
    consulta = idioma.traducir_consulta(mensaje) if lengua == "en" else mensaje
    ctx = _contexto(consulta, docente, course_id)
    motivo = fuera_de_contexto(ctx["texto"])
    if motivo and not planificar_por_reglas(consulta, docente, course_id):
        institucional = t(_RESPUESTA_INSTITUCIONAL, _RESPUESTA_INSTITUCIONAL_EN)
        respuesta = institucional if motivo == "sin_sentido" else (
            t(f"Mantengamos una comunicación respetuosa, {_trato_formal(docente) or 'por favor'}. ",
              f"Let's keep a respectful conversation, {_trato_formal(docente) or 'please'}. ") + institucional)
        return _respuesta_sin_herramientas(respuesta, "fuera_de_contexto", docente, inicio, {"motivo": motivo})
    if _PIDE_PDF.search(ctx["texto"]) and not ctx["estudiante"] and not estudiante_en_contexto(docente):
        return _respuesta_sin_herramientas(t(
            "Con gusto genero la guía oficial en PDF. ¿De qué estudiante? Indíqueme su **nombre completo** o su "
            "**cédula** (por ejemplo, «dame el pdf de Carlos Mendoza»).",
            "I'll gladly generate the official PDF guide. For which student? Tell me their **full name** or **ID "
            "number** (for example, «give me the pdf of Carlos Mendoza»)."), "aclaracion", docente, inicio)
    if _REFUERZO.search(ctx["texto"]) and not ctx["estudiante"] and not _PIDE_PDF.search(ctx["texto"]):
        return _respuesta_sin_herramientas(t(
            "Con gusto preparo un plan de apoyo. ¿Para qué estudiante? Indíqueme su **nombre completo** o su "
            "**cédula** (por ejemplo, «plan de apoyo para Carlos Mendoza»).",
            "I'll gladly prepare a support plan. For which student? Tell me their **full name** or **ID number** "
            "(for example, «support plan for Carlos Mendoza»)."), "aclaracion", docente, inicio)
    if not ctx["estudiante"] and not ctx["criterio"] and not _PANORAMA.search(ctx["texto"]):
        ambiguos = estudiantes_ambiguos(ctx["texto"], sync_service.cursos_del_docente(docente["email"]))
        if ambiguos:
            opciones = t(" o ", " or ").join(f"**{n}**" for n in ambiguos[:4])
            extra = t(" (o escriba su cédula)", " (or type their ID number)") if len(ambiguos) > 4 else ""
            return _respuesta_sin_herramientas(
                t(f"¿A qué estudiante se refiere: {opciones}{extra}?", f"Which student do you mean: {opciones}{extra}?"),
                "aclaracion", docente, inicio)
    plan, fuente = await planificar(consulta, docente, course_id)
    if not plan:
        if not (idioma.es_academico(ctx["texto"]) or idioma.es_academico(_normalizar(mensaje))):
            return _respuesta_dominio(docente, inicio)   # tema ajeno al seguimiento académico
        return _respuesta_sin_herramientas(ayuda_sin_intencion(docente), "aclaracion", docente, inicio)
    usadas = []
    for nombre, params in plan:
        t0 = time.time()
        try:
            resultado = EJECUTORES[nombre](docente, **params)
            estado = "INFO"
        except HerramientaError as ex:
            resultado, estado = {"error": str(ex), "filas": 0}, "ADVERTENCIA"
        duracion = int((time.time() - t0) * 1000)
        traza = trazabilidad(nombre, params, resultado, docente)
        repositories.insert_log(
            "AGENTE_HERRAMIENTA", estado, f"El agente invocó {nombre} ({fuente}).",
            {"herramienta": nombre, "parametros": params, "docente": docente["email"], "plan": fuente,
             "filas": resultado.get("filas", 0), "trazabilidad": traza,
             **({"error": resultado["error"]} if "error" in resultado else {})},
            duracion,
        )
        usadas.append({"herramienta": nombre, "parametros": params, "resultado": resultado, "duracion_ms": duracion,
                       "trazabilidad": traza})

    respuesta = _sin_codigos(redactar(usadas), sync_service.cursos_del_docente(docente["email"]))
    contexto_estudiante = _estudiante_de(usadas)
    repositories.insert_log(
        "AGENTE_CHAT", "EXITO",
        f"Consulta del docente atendida con {idioma.plural(len(usadas), 'herramienta', 'herramientas')}.",
        {"docente": docente["email"], "herramientas": [u["herramienta"] for u in usadas], "plan": fuente,
         "idioma": lengua, **({"estudiante_contexto": contexto_estudiante} if contexto_estudiante else {})},
        int((time.time() - inicio) * 1000),
    )
    adjuntos = [{**u["resultado"]["descarga"], **({"etiqueta": "Download PDF guide"} if lengua == "en" else {})}
                for u in usadas if "descarga" in u["resultado"]]
    return {"respuesta": respuesta, "formato": "markdown", "herramientas": usadas, "plan_fuente": fuente,
            "redaccion": "determinista_desde_herramientas", "adjuntos": adjuntos, "idioma": lengua,
            "duracion_ms": int((time.time() - inicio) * 1000)}
