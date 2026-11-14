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
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from app import repositories
from app.services import reporte_service, sync_service

logger = logging.getLogger("edumonitor.agente")

AGENT_HOST = os.getenv("AGENT_HOST") or os.getenv("AGENT_URL", "http://agent:8001")
AGENT_TIMEOUT_SECONDS = float(os.getenv("AGENT_INFERENCE_TIMEOUT_SECONDS", "10.0"))
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
        "descripcion": "Calificaciones ponderadas (ACD, Tareas, PAE, nota final, nivel, incidencias) de un curso o de "
                       "todos; opcionalmente de un estudiante por nombre o ID (U-xx) en todos sus cursos.",
        "parametros": {"course_id": "integer (opcional)", "estudiante": "string (opcional)"},
    },
    "identificar_alertas": {
        "descripcion": "Alertas tempranas activas (R1 nota < 5, R2 descenso entre unidades) de un curso o de todos.",
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
    "proponer_refuerzo": {
        "descripcion": "Analiza las falencias reales de un estudiante y redacta una propuesta de refuerzo (título, "
                       "objetivo, tarea y criterios de evaluación) lista para el Centro de Alertas.",
        "parametros": {"student_query": "string (nombre o ID U-xx del estudiante)", "course_id": "integer (opcional)"},
    },
}

NOMBRE_COMPONENTE = {"acd": "ACD", "tareas": "Tareas", "pae": "PAE"}
PESO_COMPONENTE = {"acd": 40, "tareas": 30, "pae": 30}
NIVEL_TEXTO = {"CRITICO": "crítico", "EN_RIESGO": "en riesgo", "ACEPTABLE": "aceptable"}
ESTADO_ALERTA_TEXTO = {"ABIERTA": "abierta", "ATENDIDA": "en atención", "PUBLICADO": "refuerzo publicado"}
TENDENCIA_TEXTO = {"SUBE": "al alza", "BAJA": "a la baja", "ESTABLE": "estable"}


class HerramientaError(Exception):
    """Parámetros inválidos o curso no autorizado."""


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto.lower()).strip()


def _nombre_curso(fullname: str) -> str:
    """'(SOF) PROGRAMACION ORIENTADA A OBJETOS - A' -> 'Programacion orientada a objetos (A)'."""
    nombre = re.sub(r"^\(\w+\)\s*", "", fullname or "").strip()
    paralelo = re.search(r"\s+-\s+([A-Z])$", nombre)
    if paralelo:
        nombre = nombre[:paralelo.start()]
    nombre = nombre.capitalize()
    return f"{nombre} ({paralelo.group(1)})" if paralelo else nombre


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
    return filtro == _normalizar(e["id_number"]) or filtro in _normalizar(e["nombres"] or "")


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


def obtener_calificaciones(docente: dict, course_id: Optional[int] = None,
                           estudiante: Optional[str] = None) -> Dict[str, Any]:
    filtro = _normalizar(estudiante) if estudiante else None
    resultado = []
    for c in _cursos(docente, course_id):
        for e in c["estudiantes"]:
            if filtro and not _coincide(e, filtro):
                continue
            resultado.append({
                "curso_id": c["id"], "curso": c["shortname"], "curso_nombre": c["fullname"],
                "id_number": e["id_number"], "nombres": e["nombres"],
                "acd": e["acd"], "tareas": e["tareas"], "pae": e["pae"], "nota_final": e["nota_final"],
                "nivel_riesgo": e["nivel_riesgo"], "tendencia": e.get("tendencia"),
                "promedios_unidad": e.get("promedios_unidad") or {},
                "incidencias": [f"{a['id_number']} {_incidencia(a)}" for a in e["actividades"] if _incidencia(a)],
            })
    if filtro and not resultado:
        raise HerramientaError(f"No se encontró al estudiante «{estudiante}» en los cursos consultados.")
    return {"calificaciones": resultado, "filas": len(resultado), "estudiante": estudiante}


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
             (f": {foco.split(':')[-1].strip()}" if foco else "") + f" — {curso['shortname']}"

    objetivo = (f"Que {e['nombres']} consolide los aprendizajes de la Unidad {num_unidad} "
                f"(promedio actual {_f(unidades[unidad_critica])}/10)" if unidad_critica
                else f"Que {e['nombres']} consolide los aprendizajes evaluados del curso")
    if componente_debil:
        objetivo += f", fortalezca el componente {NOMBRE_COMPONENTE[componente_debil]} ({_f(componentes[componente_debil])}/10)"
    pendientes_entrega = [i for i in incidencias if i["tipo"] in ("SIN_ENTREGA", "NOTA_0")]
    if pendientes_entrega:
        objetivo += f" y regularice {len(pendientes_entrega)} entrega(s) con nota 0 o sin entrega"
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


EJECUTORES: Dict[str, Callable[..., Dict[str, Any]]] = {
    "listar_cursos_autorizados": listar_cursos_autorizados,
    "obtener_calificaciones": obtener_calificaciones,
    "identificar_alertas": identificar_alertas,
    "generar_resumen": generar_resumen,
    "analizar_actividades": analizar_actividades,
    "proponer_refuerzo": proponer_refuerzo,
}
_PARAMETROS_VALIDOS = {
    "listar_cursos_autorizados": set(),
    "obtener_calificaciones": {"course_id", "estudiante"},
    "identificar_alertas": {"course_id", "regla"},
    "generar_resumen": {"course_id"},
    "analizar_actividades": {"course_id"},
    "proponer_refuerzo": {"student_query", "course_id"},
}


# =============================================================================== Planificación
_GLOBAL = re.compile(r"\b(mis (\d+|dos|tres|cuatro|cinco) (cursos|materias|asignaturas)|todas? (mis |las |los )?"
                     r"(materias|cursos|asignaturas)|mis materias|mis asignaturas|en total|en general|global|"
                     r"todos mis|cada (curso|materia)|entre (mis )?cursos)\b")
_REFUERZO = re.compile(r"\b(refuerzo|reforzar|plan de mejora|recuperacion|nivelacion|actividad de apoyo|"
                       r"prepar\w* (una |un )?(actividad|tarea))\b")
_ACTIVIDADES = re.compile(r"\b((actividad|actividades|tarea|tareas|evaluacion|evaluaciones)\b.*\b(menor|bajo|baja|"
                          r"peor|peores|dificil\w*|problema\w*|rendimiento|cuesta)|(menor|peor|bajo) rendimiento)")
_CURSOS = re.compile(r"\b(mis cursos|que cursos|cuales cursos|cursos tengo|lista de cursos|listar cursos|"
                     r"cuantos cursos|cuantos estudiantes|cuantos alumnos|cuantas materias|materias tengo)\b")


def _curso_mencionado(texto: str, cursos: List[Dict[str, Any]]) -> Optional[int]:
    for c in cursos:
        codigo = _normalizar(c["shortname"])
        partes = [p for p in codigo.split("-") if p and p != "sof"]
        abreviatura = partes[0] if partes else codigo
        if codigo in texto or re.search(rf"\b{re.escape(abreviatura)}\b", texto):
            return c["id"]
        palabras = [p for p in re.findall(r"[a-z]{5,}", _normalizar(c["fullname"] or ""))]
        if palabras and sum(1 for p in palabras if p in texto) >= min(2, len(palabras)):
            return c["id"]
    return None


def _estudiante_mencionado(texto: str, cursos: List[Dict[str, Any]]) -> Optional[str]:
    codigo = re.search(r"\bu-?\d{2}\b", texto)
    if codigo:
        valor = codigo.group(0).upper()
        return valor if "-" in valor else f"U-{valor[1:]}"
    for c in cursos:
        for e in c["estudiantes"]:
            partes = [p for p in _normalizar(e["nombres"] or "").split() if len(p) > 3]
            if len(partes) >= 2 and sum(1 for p in partes if re.search(rf"\b{p}\b", texto)) >= 2:
                return e["nombres"]
            if partes and re.search(rf"\b{partes[-1]}\b", texto) and len(partes[-1]) > 5:
                return e["nombres"]
    return None


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
            "global": global_, "contexto": course_id}


def planificar_por_reglas(mensaje: str, docente: dict, course_id: Optional[int] = None) -> List[Tuple[str, Dict]]:
    """Planificador determinista de respaldo: intención por palabras clave + curso/estudiante mencionados."""
    ctx = _contexto(mensaje, docente, course_id)
    texto, curso, estudiante = ctx["texto"], ctx["curso"], ctx["estudiante"]
    base = {"course_id": curso} if curso else {}
    plan: List[Tuple[str, Dict]] = []

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
    if re.search(r"\b(alerta|alertas|riesgo|critic\w*|atencion|ayuda|reprob\w*|descenso|r1|r2|refuerzo)\b", texto):
        regla = "R1" if re.search(r"\b(r1|critic\w*)\b", texto) and "r2" not in texto else (
            "R2" if re.search(r"\b(r2|descenso|baja)\b", texto) else None)
        plan.append(("identificar_alertas", {**base, **({"regla": regla} if regla else {})}))
    resumen = r"\b(resumen|informe|reporte|panorama|estado del curso|situacion)\b"
    if re.search(resumen, texto) or (not estudiante and re.search(r"\b(como va|como esta|como van)\b", texto)):
        plan.append(("generar_resumen", base))
    if not plan:  # sin intención clara: panorama general con datos reales
        plan = [("listar_cursos_autorizados", {}), ("identificar_alertas", base), ("generar_resumen", base)]
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
        elif nombre != "listar_cursos_autorizados":
            if ctx["curso"]:
                params["course_id"] = ctx["curso"]
            elif ctx["global"] or ctx["estudiante"]:
                params.pop("course_id", None)
            if nombre == "obtener_calificaciones" and ctx["estudiante"]:
                params["estudiante"] = ctx["estudiante"]
        resuelto.append((nombre, params))
    return resuelto


async def planificar(mensaje: str, docente: dict, course_id: Optional[int]) -> Tuple[List[Tuple[str, Dict]], str]:
    """Plan del LLM (vía microservicio del agente) validado; si falla, planificador por reglas."""
    cursos = [{"id": c["id"], "shortname": c["shortname"], "fullname": c["fullname"]}
              for c in sync_service.cursos_del_docente(docente["email"])]
    try:
        async with httpx.AsyncClient(timeout=AGENT_TIMEOUT_SECONDS) as client:
            resp = await client.post(f"{AGENT_HOST}/api/v1/chat/plan", json={
                "mensaje": mensaje, "cursos": cursos, "course_id": course_id,
                "herramientas": [{"nombre": n, **d} for n, d in CATALOGO.items()],
            })
        if resp.status_code == 200:
            data = resp.json()
            plan = _resolver_entidades(_validar_plan(data.get("llamadas"), docente), mensaje, docente, course_id)
            if plan:
                reglas = planificar_por_reglas(mensaje, docente, course_id)
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
    lineas = [f"- **{c['shortname']}** · {_nombre_curso(c['fullname'])}: {c['total_estudiantes']} "
              f"estudiantes, promedio **{c['promedio']:.2f}/10** ({c['criticos']} crítico(s), {c['en_riesgo']} en riesgo)"
              for c in r["cursos"]]
    lineas.append(f"\nEn conjunto hay **{t['criticos']}** matrícula(s) en nivel crítico y **{t['en_riesgo']}** en riesgo.")
    return "Cursos asignados", clave, lineas


def _seccion_calificaciones(r: Dict[str, Any]) -> Seccion:
    filas = r["calificaciones"]
    if r.get("estudiante"):
        nombre = filas[0]["nombres"]
        criticos = sum(1 for f in filas if f["nivel_riesgo"] == "CRITICO")
        promedio = sum(f["nota_final"] for f in filas) / len(filas)
        clave = (f"**{nombre}** ({filas[0]['id_number']}) está matriculado(a) en **{len(filas)} curso(s)** con promedio "
                 f"**{promedio:.2f}/10**; nivel crítico en {criticos} de {len(filas)}.")
        lineas = []
        for f in sorted(filas, key=lambda x: x["nota_final"]):
            lineas.append(f"- **{f['curso']}**: **{f['nota_final']:.2f}/10** ({NIVEL_TEXTO.get(f['nivel_riesgo'], f['nivel_riesgo'])}) · "
                          f"ACD {_f(f['acd'])} · Tareas {_f(f['tareas'])} · PAE {_f(f['pae'])} · tendencia "
                          f"{TENDENCIA_TEXTO.get(f['tendencia'], (f['tendencia'] or '—').lower())}")
            if f["incidencias"]:
                lineas.append("  - Incidencias: " + ", ".join(
                    f"{i.split()[0]} ({_INCIDENCIA_TEXTO.get(i.split()[1], i.split()[1])})" for i in f["incidencias"]))
        return f"Calificaciones de {nombre}", clave, lineas

    por_curso: Dict[str, List[Dict[str, Any]]] = {}
    for f in filas:
        por_curso.setdefault(f["curso"], []).append(f)
    criticos = [f for f in filas if f["nivel_riesgo"] == "CRITICO"]
    clave = (f"Revisé **{len(filas)} calificaciones** en {len(por_curso)} curso(s): **{len(criticos)} en nivel crítico** "
             f"y {sum(1 for f in filas if f['nivel_riesgo'] == 'EN_RIESGO')} en riesgo.")
    lineas = []
    for curso, lista in por_curso.items():
        lista.sort(key=lambda x: x["nota_final"])
        aprobados = sum(1 for f in lista if f["nota_final"] >= UMBRAL_APROBACION)
        lineas.append(f"- **{curso}** ({len(lista)} estudiantes, {aprobados} con nota ≥ 7.00)")
        seguimiento = [f for f in lista if f["nivel_riesgo"] != "ACEPTABLE"]
        for f in seguimiento[:6]:
            lineas.append(f"  - {f['nombres']}: **{f['nota_final']:.2f}/10** ({NIVEL_TEXTO.get(f['nivel_riesgo'])})"
                          + (f" · {len(f['incidencias'])} incidencia(s)" if f["incidencias"] else ""))
        if not seguimiento:
            lineas.append("  - Todos los estudiantes tienen nota ≥ 7.00.")
    return "Calificaciones", clave, lineas


def _seccion_alertas(r: Dict[str, Any]) -> Seccion:
    alertas = sorted(r["alertas"], key=lambda a: (a.get("nota_final") is None, a.get("nota_final") or 0))
    if not alertas:
        return "Alertas tempranas", "No hay alertas activas para el criterio consultado.", []
    abiertas = sum(1 for a in alertas if a["estado"] == "ABIERTA")
    clave = (f"Hay **{len(alertas)} alerta(s) activa(s)**; {abiertas} sigue(n) abierta(s) y requiere(n) "
             f"atención prioritaria.")
    lineas = [f"- **{a['nombres']}** ({a['curso']}) · {a['regla'].split('_')[0]} "
              f"{'nota crítica' if a['regla'].startswith('R1') else 'descenso sostenido'} · nota **{_f(a.get('nota_final'))}/10**"
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
            f"- **Niveles:** {m['criticos']} crítico(s), {m['en_riesgo']} en riesgo y {m['aceptables']} aceptable(s) "
            f"de {m['total_estudiantes']}",
            f"- **Entregas:** {d['cero']} con nota 0, {d['sin_entrega']} sin entrega y {d['pendiente']} pendiente(s) "
            f"de {d['total_registros']} registros",
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
            extras.append(f"{a['pendientes']} pendiente(s)")
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
    return "Propuesta de refuerzo", clave, lineas


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
    return []


def redactar(usadas: List[Dict[str, Any]]) -> str:
    """Respuesta en Markdown: resumen ejecutivo + una sección por resultado (sólo datos de las herramientas)."""
    secciones = [s for u in usadas for s in _secciones(u["herramienta"], u["resultado"])]
    if not secciones:
        return "No encontré información para responder. Pruebe a sincronizar con Moodle UTA."
    if len(secciones) == 1:
        titulo, clave, lineas = secciones[0]
        return "\n".join([clave, ""] + lineas).strip()
    partes = ["**Resumen ejecutivo**"] + [f"- {clave}" for _, clave, _ in secciones]
    for titulo, _, lineas in secciones:
        if lineas:
            partes += ["", f"### {titulo}"] + lineas
    return "\n".join(partes).strip()


async def conversar(mensaje: str, docente: dict, course_id: Optional[int] = None) -> Dict[str, Any]:
    inicio = time.time()
    plan, fuente = await planificar(mensaje, docente, course_id)
    usadas = []
    for nombre, params in plan:
        t0 = time.time()
        try:
            resultado = EJECUTORES[nombre](docente, **params)
            estado = "INFO"
        except HerramientaError as ex:
            resultado, estado = {"error": str(ex), "filas": 0}, "ADVERTENCIA"
        duracion = int((time.time() - t0) * 1000)
        repositories.insert_log(
            "AGENTE_HERRAMIENTA", estado, f"El agente invocó {nombre} ({fuente}).",
            {"herramienta": nombre, "parametros": params, "docente": docente["email"], "plan": fuente,
             "filas": resultado.get("filas", 0), **({"error": resultado["error"]} if "error" in resultado else {})},
            duracion,
        )
        usadas.append({"herramienta": nombre, "parametros": params, "resultado": resultado, "duracion_ms": duracion})

    respuesta = redactar(usadas)
    repositories.insert_log(
        "AGENTE_CHAT", "EXITO", f"Consulta del docente atendida con {len(usadas)} herramienta(s).",
        {"docente": docente["email"], "herramientas": [u["herramienta"] for u in usadas], "plan": fuente},
        int((time.time() - inicio) * 1000),
    )
    return {"respuesta": respuesta, "formato": "markdown", "herramientas": usadas, "plan_fuente": fuente,
            "redaccion": "determinista_desde_herramientas", "duracion_ms": int((time.time() - inicio) * 1000)}
