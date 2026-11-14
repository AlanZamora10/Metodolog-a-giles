"""
Agente conversacional con herramientas (Fase A) — POST /api/v1/agent/chat.

Flujo (RN-15: el cálculo es determinista; la IA sólo decide qué consultar):
  1. Planificación: el microservicio del agente (Ollama llama3.2:1b con *tool calling*) propone qué
     herramientas invocar. Si no responde a tiempo o propone algo inválido, se usa un planificador por
     reglas (palabras clave, curso y estudiante mencionados).
  2. Ejecución: cada herramienta consulta datos REALES del sistema (sincronización con Moodle persistida y
     alertas en la base), validando que el curso pertenezca al docente. Cada invocación se registra en
     `logs_sistema` (herramienta, parámetros, docente, origen del plan, filas devueltas).
  3. Respuesta: se redacta sólo con los resultados de las herramientas (sin datos inventados).
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

CATALOGO: Dict[str, Dict[str, Any]] = {
    "listar_cursos_autorizados": {
        "descripcion": "Lista los cursos de Moodle en los que el docente es profesor, con número de estudiantes y promedio.",
        "parametros": {},
    },
    "obtener_calificaciones": {
        "descripcion": "Devuelve las calificaciones ponderadas (ACD, Tareas, PAE, nota final, nivel) de un curso; "
                       "opcionalmente de un estudiante por nombre o ID number (U-xx).",
        "parametros": {"course_id": "integer (opcional)", "estudiante": "string (opcional)"},
    },
    "identificar_alertas": {
        "descripcion": "Lista las alertas tempranas activas (R1 nota < 5, R2 descenso entre unidades) de un curso o de todos.",
        "parametros": {"course_id": "integer (opcional)", "regla": "R1 | R2 (opcional)"},
    },
    "generar_resumen": {
        "descripcion": "Genera el resumen del curso: métricas, distribución de estados, hallazgos y recomendaciones.",
        "parametros": {"course_id": "integer (opcional)"},
    },
}


class HerramientaError(Exception):
    """Parámetros inválidos o curso no autorizado."""


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto.lower()).strip()


# =============================================================================== Herramientas
def _cursos(docente: dict, course_id: Optional[int]) -> List[Dict[str, Any]]:
    propios = sync_service.cursos_del_docente(docente["email"])
    if course_id is None:
        return propios
    curso = next((c for c in propios if c["id"] == int(course_id)), None)
    if curso is None:
        raise HerramientaError(f"El curso {course_id} no existe o no pertenece al docente.")
    return [curso]


def listar_cursos_autorizados(docente: dict) -> Dict[str, Any]:
    cursos = [sync_service.resumen_curso(c) for c in sync_service.cursos_del_docente(docente["email"])]
    return {"cursos": cursos, "filas": len(cursos)}


def obtener_calificaciones(docente: dict, course_id: Optional[int] = None,
                           estudiante: Optional[str] = None) -> Dict[str, Any]:
    filtro = _normalizar(estudiante) if estudiante else None
    resultado = []
    for c in _cursos(docente, course_id):
        for e in c["estudiantes"]:
            if filtro and filtro not in (_normalizar(e["id_number"]), ) and filtro not in _normalizar(e["nombres"] or ""):
                continue
            resultado.append({
                "curso_id": c["id"], "curso": c["shortname"], "id_number": e["id_number"], "nombres": e["nombres"],
                "acd": e["acd"], "tareas": e["tareas"], "pae": e["pae"], "nota_final": e["nota_final"],
                "nivel_riesgo": e["nivel_riesgo"], "tendencia": e.get("tendencia"),
                "incidencias": [f"{a['id_number']} {'NOTA_0' if a['estado'] == 'CALIFICADO' else a['estado']}"
                                for a in e["actividades"] if a["estado"] != "CALIFICADO" or a["nota"] == 0],
            })
    if filtro and not resultado:
        raise HerramientaError(f"No se encontró al estudiante «{estudiante}» en los cursos consultados.")
    return {"calificaciones": resultado, "filas": len(resultado)}


def identificar_alertas(docente: dict, course_id: Optional[int] = None, regla: Optional[str] = None) -> Dict[str, Any]:
    ids = {c["id"] for c in _cursos(docente, course_id)}
    codigo_regla = {"R1": "R1_NOTA_CRITICA", "R2": "R2_DESCENSO"}.get((regla or "").upper()[:2])
    alertas = [
        {"id": a["id"], "curso": a["curso_codigo"], "curso_id": a["curso_id"], "id_number": a["id_number"],
         "nombres": a["nombres"], "regla": a["regla"], "nota_final": a.get("nota_final"),
         "pendiente": a.get("pendiente"), "estado": a["estado"]}
        for a in repositories.list_alertas()
        if a.get("curso_id") in ids and a["estado"] in ("ABIERTA", "ATENDIDA", "PUBLICADO")
        and (codigo_regla is None or a["regla"] == codigo_regla)
    ]
    return {"alertas": alertas, "filas": len(alertas)}


def generar_resumen(docente: dict, course_id: Optional[int] = None) -> Dict[str, Any]:
    resumenes = []
    for c in _cursos(docente, course_id):
        r = reporte_service.construir_reporte(c, repositories.list_alertas(course_id=c["id"]),
                                              sync_service.SYNC_STATE.get("ultima_sincronizacion"))
        resumenes.append({"curso": c["shortname"], "curso_id": c["id"], "metricas": r["metricas"],
                          "distribucion_estados": r["distribucion_estados"], "hallazgos": r["hallazgos"],
                          "recomendaciones": r["recomendaciones"]})
    return {"resumenes": resumenes, "filas": len(resumenes)}


EJECUTORES: Dict[str, Callable[..., Dict[str, Any]]] = {
    "listar_cursos_autorizados": listar_cursos_autorizados,
    "obtener_calificaciones": obtener_calificaciones,
    "identificar_alertas": identificar_alertas,
    "generar_resumen": generar_resumen,
}
_PARAMETROS_VALIDOS = {
    "listar_cursos_autorizados": set(),
    "obtener_calificaciones": {"course_id", "estudiante"},
    "identificar_alertas": {"course_id", "regla"},
    "generar_resumen": {"course_id"},
}


# =============================================================================== Planificación
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


def planificar_por_reglas(mensaje: str, docente: dict, course_id: Optional[int] = None) -> List[Tuple[str, Dict]]:
    """Planificador determinista de respaldo: intención por palabras clave + curso/estudiante mencionados."""
    texto = _normalizar(mensaje)
    cursos = sync_service.cursos_del_docente(docente["email"])
    curso = course_id or _curso_mencionado(texto, cursos)
    estudiante = _estudiante_mencionado(texto, cursos)
    base = {"course_id": curso} if curso else {}
    plan: List[Tuple[str, Dict]] = []

    if re.search(r"\b(mis cursos|que cursos|cuales cursos|cursos tengo|lista de cursos|listar cursos)\b", texto):
        plan.append(("listar_cursos_autorizados", {}))
    if estudiante or re.search(r"\b(nota|notas|calificacion|calificaciones|promedio de|rendimiento de)\b", texto):
        plan.append(("obtener_calificaciones", {**base, **({"estudiante": estudiante} if estudiante else {})}))
    if re.search(r"\b(alerta|alertas|riesgo|critic\w*|atencion|ayuda|reprob\w*|descenso|r1|r2)\b", texto):
        regla = "R1" if re.search(r"\b(r1|critic\w*)\b", texto) and "r2" not in texto else (
            "R2" if re.search(r"\b(r2|descenso|baja)\b", texto) else None)
        plan.append(("identificar_alertas", {**base, **({"regla": regla} if regla else {})}))
    if re.search(r"\b(resumen|informe|reporte|panorama|estado del curso|como va|como esta|situacion)\b", texto):
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
    El LLM decide QUÉ herramientas usar; el curso y el estudiante que el mensaje menciona explícitamente
    se resuelven de forma determinista y prevalecen sobre los que proponga el modelo (evita, p. ej., que
    «Estructura de Datos» termine consultando otro curso).
    """
    texto = _normalizar(mensaje)
    cursos = sync_service.cursos_del_docente(docente["email"])
    curso = course_id or _curso_mencionado(texto, cursos)
    estudiante = _estudiante_mencionado(texto, cursos)
    resuelto = []
    for nombre, params in plan:
        params = dict(params)
        if nombre != "listar_cursos_autorizados" and curso:
            params["course_id"] = curso
        if nombre == "obtener_calificaciones" and estudiante:
            params["estudiante"] = estudiante
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
            plan = _validar_plan(data.get("llamadas"), docente)
            if plan:
                plan = _resolver_entidades(plan, mensaje, docente, course_id)
                # El modelo pequeño puede omitir la herramienta que la pregunta pide explícitamente:
                # se complementa con las del planificador por reglas (sin duplicar herramientas).
                usadas = {n for n, _ in plan}
                extra = [(n, p) for n, p in planificar_por_reglas(mensaje, docente, course_id) if n not in usadas]
                fuente = data.get("fuente", "ollama_slm") + ("+reglas" if extra else "")
                return (plan + extra)[:MAX_HERRAMIENTAS_POR_MENSAJE], fuente
    except Exception as ex:  # agente caído o lento: respaldo determinista
        logger.info("Planificador del agente no disponible (%s); se usa el de reglas.", ex.__class__.__name__)
    return planificar_por_reglas(mensaje, docente, course_id), "reglas_deterministas"


# =============================================================================== Redacción (sólo con datos)
def _texto(nombre: str, r: Dict[str, Any]) -> str:
    if "error" in r:
        return f"No pude ejecutar {nombre}: {r['error']}"
    if nombre == "listar_cursos_autorizados":
        if not r["cursos"]:
            return "No tiene cursos sincronizados. Pulse «Sincronizar» para importarlos desde Moodle."
        return f"Tiene {r['filas']} curso(s) autorizado(s): " + "; ".join(
            f"{c['shortname']} ({c['total_estudiantes']} estudiantes, promedio {c['promedio']:.2f})" for c in r["cursos"]) + "."
    if nombre == "obtener_calificaciones":
        filas = r["calificaciones"]
        if len(filas) <= 3:
            return " ".join(
                f"{f['nombres']} ({f['id_number']}) en {f['curso']}: nota {f['nota_final']:.2f}/10 ({f['nivel_riesgo']}); "
                f"ACD {f['acd'] if f['acd'] is not None else '—'}, Tareas {f['tareas'] if f['tareas'] is not None else '—'}, "
                f"PAE {f['pae'] if f['pae'] is not None else '—'}"
                + (f"; incidencias: {', '.join(f['incidencias'])}." if f["incidencias"] else ".")
                for f in filas)
        criticos = [f for f in filas if f["nivel_riesgo"] == "CRITICO"]
        return (f"Consulté {len(filas)} calificaciones. Críticos: "
                + (", ".join(f"{f['nombres']} ({f['nota_final']:.2f}, {f['curso']})" for f in criticos) or "ninguno") + ".")
    if nombre == "identificar_alertas":
        if not r["alertas"]:
            return "No hay alertas activas para el criterio consultado."
        return f"Hay {r['filas']} alerta(s) activa(s): " + "; ".join(
            f"{a['nombres']} ({a['curso']}, {a['regla'].split('_')[0]}, nota {a['nota_final']:.2f}, {a['estado']})"
            for a in r["alertas"]) + "."
    if nombre == "generar_resumen":
        return " ".join(f"[{s['curso']}] " + " ".join(s["hallazgos"][:3]) + " Recomendación: " + s["recomendaciones"][0]
                        for s in r["resumenes"]) or "No hay cursos para resumir."
    return ""


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
        repositories.insert_log(
            "AGENTE_HERRAMIENTA", estado, f"El agente invocó {nombre} ({fuente}).",
            {"herramienta": nombre, "parametros": params, "docente": docente["email"], "plan": fuente,
             "filas": resultado.get("filas", 0), **({"error": resultado["error"]} if "error" in resultado else {})},
            int((time.time() - t0) * 1000),
        )
        usadas.append({"herramienta": nombre, "parametros": params, "resultado": resultado})

    respuesta = "\n".join(t for t in (_texto(u["herramienta"], u["resultado"]) for u in usadas) if t)
    repositories.insert_log(
        "AGENTE_CHAT", "EXITO", f"Consulta del docente atendida con {len(usadas)} herramienta(s).",
        {"docente": docente["email"], "herramientas": [u["herramienta"] for u in usadas], "plan": fuente},
        int((time.time() - inicio) * 1000),
    )
    return {"respuesta": respuesta, "herramientas": usadas, "plan_fuente": fuente,
            "redaccion": "determinista_desde_herramientas", "duracion_ms": int((time.time() - inicio) * 1000)}
