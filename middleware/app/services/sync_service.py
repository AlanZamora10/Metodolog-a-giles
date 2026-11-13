"""
Servicio de sincronización Moodle UTA -> EduMonitor AI.

Extrae los cursos del portafolio, TODOS sus docentes/estudiantes matriculados y el libro
de calificaciones, calcula la nota ponderada, el nivel de riesgo y la tendencia, guarda el
resultado en PostgreSQL (Sprint 3) y deja una copia en memoria (SYNC_STATE) para el panel.

Las actividades se clasifican por su ID number institucional:
  Ux-Ay -> ACD (40%)   Ux-Ty -> Tareas (30%)   Ux-Py -> PAE (30%)
  Unidades 1-2 -> Parcial 1   Unidades 3-4 -> Parcial 2
Cada componente es el promedio (sobre 10) de sus actividades calificadas:
  - nota numérica                 -> cuenta (incluye 0)
  - sin nota + "SIN ENTREGA"      -> cuenta como 0
  - sin nota + "PENDIENTE"        -> no cuenta (pendiente de revisión)
  - sin nota y sin comentario     -> no cuenta (aún no evaluada)

Tendencia (R2): pendiente de regresión lineal sobre el promedio de cada unidad evaluada (U1, U2, ...).
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app import database, repositories
from app.config import settings
from app.services.grade_calculator import GradeCalculator
from app.services.moodle_client import MoodleClient

logger = logging.getLogger("edumonitor.sync")

TEACHER_ROLES = {"editingteacher", "teacher"}
STUDENT_ROLES = {"student"}
COMPONENTES = ("ACD", "TAREAS", "PAE")
_PATRON_ACTIVIDAD = re.compile(r"^U(\d+)-([ATP])(\d+)$", re.IGNORECASE)
_LETRA_COMPONENTE = {"A": "ACD", "T": "TAREAS", "P": "PAE"}
_PRIORIDAD_ESTADO = {"CALIFICADO": 0, "PENDIENTE": 1, "SIN_ENTREGA": 2}

# Última sincronización (caché en memoria de lo persistido en la base)
SYNC_STATE: Dict[str, Any] = {"ultima_sincronizacion": None, "moodle": None, "cursos": []}


def _roles(user: Dict[str, Any]) -> set:
    return {r.get("shortname") for r in user.get("roles", [])}


def _clasificar(item: Dict[str, Any]) -> Optional[Tuple[str, int]]:
    """(componente, unidad) de un ítem con ID number Ux-[ATP]y; None si no pertenece al esquema."""
    match = _PATRON_ACTIVIDAD.match((item.get("idnumber") or "").strip())
    if not match:
        return None
    return _LETRA_COMPONENTE[match.group(2).upper()], int(match.group(1))


def parcial_de_unidad(unidad: int) -> int:
    return 1 if unidad <= 2 else 2


def _estado_actividad(item: Dict[str, Any]) -> Tuple[str, Optional[float]]:
    """Devuelve (estado, nota sobre 10 que cuenta para el promedio o None si no cuenta)."""
    feedback = (item.get("feedback") or "").upper()
    raw = item.get("graderaw")
    if raw is not None:
        grademax = float(item.get("grademax") or 10) or 10.0
        nota = round(float(raw) * 10.0 / grademax, 2)
        return ("SIN_ENTREGA" if "SIN ENTREGA" in feedback else "CALIFICADO"), nota
    if "SIN ENTREGA" in feedback:
        return "SIN_ENTREGA", 0.0
    if "PENDIENTE" in feedback:
        return "PENDIENTE", None
    return "NO_EVALUADA", None


def _promedio(valores: List[float]) -> Optional[float]:
    return round(sum(valores) / len(valores), 2) if valores else None


def metricas(actividades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Componentes, nota ponderada, nivel, promedios por unidad y tendencia de un conjunto de actividades."""
    valores: Dict[str, List[float]] = {c: [] for c in COMPONENTES}
    por_unidad: Dict[int, List[float]] = {}
    for a in actividades:
        if a["nota"] is None:
            continue
        valores[a["componente"]].append(a["nota"])
        por_unidad.setdefault(a["unidad"], []).append(a["nota"])

    promedios = {c: _promedio(v) for c, v in valores.items()}
    # Un componente sin ninguna actividad que cuente aporta 0.00 a la nota ponderada.
    nota_final = GradeCalculator.calculate_weighted_grade(
        autonomo=promedios["ACD"] or 0.0,
        tareas=promedios["TAREAS"] or 0.0,
        pae=promedios["PAE"] or 0.0,
    )
    unidades = {f"U{u}": _promedio(por_unidad[u]) for u in sorted(por_unidad)}
    tendencia = GradeCalculator.calculate_trend(list(unidades.values()))
    return {
        "acd": promedios["ACD"], "tareas": promedios["TAREAS"], "pae": promedios["PAE"],
        "nota_final": nota_final,
        # Decisión Sprint 3: el semáforo depende sólo de la nota; la pendiente alimenta la regla R2.
        "nivel_riesgo": GradeCalculator.classify_risk(nota_final),
        "promedios_unidad": unidades,
        "pendiente": tendencia["slope"],
        "tendencia": tendencia["trend"],
        "probabilidad_aprobacion": tendencia["probability_approval"],
    }


def construir_estudiante(user: Dict[str, Any], gradeitems: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convierte un usuario de Moodle + sus ítems de calificación en el registro analítico."""
    estados: Dict[str, str] = {}
    actividades: List[Dict[str, Any]] = []

    for item in gradeitems:
        clasif = _clasificar(item)
        if not clasif:
            continue
        comp, unidad = clasif
        estado, nota = _estado_actividad(item)
        if estado == "NO_EVALUADA":
            continue
        actividades.append({
            "id_number": item.get("idnumber"),
            "nombre": item.get("itemname"),
            "componente": comp,
            "unidad": unidad,
            "parcial": parcial_de_unidad(unidad),
            "nota": nota,
            "estado": estado,
        })
        # El estado del componente refleja la incidencia más relevante: SIN_ENTREGA > PENDIENTE > CALIFICADO
        if _PRIORIDAD_ESTADO[estado] >= _PRIORIDAD_ESTADO[estados.get(comp, "CALIFICADO")]:
            estados[comp] = estado

    actividades.sort(key=lambda a: a["id_number"])
    m = metricas(actividades)
    contadas = [a for a in actividades if a["nota"] is not None]
    parciales_evaluados = sorted({a["parcial"] for a in contadas}) or [1]
    por_parcial = {p: metricas([a for a in actividades if a["parcial"] == p]) for p in parciales_evaluados}

    return {
        "moodle_id": user.get("id"),
        "id_number": user.get("idnumber") or f"MDL-{user.get('id')}",
        "nombres": user.get("fullname"),
        "email": user.get("email"),
        "acd": m["acd"],
        "tareas": m["tareas"],
        "pae": m["pae"],
        "estados": estados,
        "actividades": actividades,
        "nota_final": m["nota_final"],
        "nivel_riesgo": m["nivel_riesgo"],
        "promedios_unidad": m["promedios_unidad"],
        "pendiente": m["pendiente"],
        "tendencia": m["tendencia"],
        "probabilidad_aprobacion": m["probabilidad_aprobacion"],
        "regla_alerta": GradeCalculator.evaluate_alert_rule(m["nota_final"], m["pendiente"]),
        "parcial_vigente": parciales_evaluados[-1],
        "por_parcial": por_parcial,
    }


def resumen_curso(curso: Dict[str, Any]) -> Dict[str, Any]:
    est = curso["estudiantes"]
    total = len(est)
    return {
        "id": curso["id"],
        "shortname": curso["shortname"],
        "fullname": curso["fullname"],
        "total_estudiantes": total,
        "promedio": round(sum(e["nota_final"] for e in est) / total, 2) if total else 0.0,
        "criticos": sum(1 for e in est if e["nivel_riesgo"] == "CRITICO"),
        "en_riesgo": sum(1 for e in est if e["nivel_riesgo"] == "EN_RIESGO"),
        "aceptables": sum(1 for e in est if e["nivel_riesgo"] == "ACEPTABLE"),
        "alertas_r1": sum(1 for e in est if e.get("regla_alerta") == GradeCalculator.REGLA_R1),
        "alertas_r2": sum(1 for e in est if e.get("regla_alerta") == GradeCalculator.REGLA_R2),
    }


def cursos_del_docente(email: str) -> List[Dict[str, Any]]:
    correo = email.strip().lower()
    return [c for c in SYNC_STATE["cursos"] if correo in c["docentes"]]


def respuesta_para_docente(email: str) -> Dict[str, Any]:
    cursos = cursos_del_docente(email)
    estudiantes: Dict[str, Dict[str, Any]] = {}
    for c in cursos:
        for e in c["estudiantes"]:
            estudiantes.setdefault(e["id_number"], {k: e[k] for k in ("id_number", "nombres", "email")})
    return {
        "ultima_sincronizacion": SYNC_STATE["ultima_sincronizacion"],
        "moodle": SYNC_STATE["moodle"],
        "persistencia": SYNC_STATE.get("persistencia"),
        "total_cursos": len(cursos),
        "total_estudiantes": len(estudiantes),
        "cursos": [resumen_curso(c) for c in cursos],
        "estudiantes": sorted(estudiantes.values(), key=lambda e: e["id_number"]),
    }


def _construir_curso(curso_moodle: Dict[str, Any], usuarios: List[Dict[str, Any]],
                     usergrades: Dict[Any, List[Dict[str, Any]]]) -> Dict[str, Any]:
    docentes = [u for u in usuarios if _roles(u) & TEACHER_ROLES]
    alumnos = [u for u in usuarios if _roles(u) & STUDENT_ROLES]
    return {
        "id": curso_moodle["id"],
        "shortname": curso_moodle.get("shortname"),
        "fullname": curso_moodle.get("fullname"),
        "docentes": [(u.get("email") or "").lower() for u in docentes],
        "docente_titular": docentes[0].get("fullname") if docentes else None,
        "estudiantes": sorted(
            (construir_estudiante(u, usergrades.get(u["id"], [])) for u in alumnos),
            key=lambda e: e["id_number"],
        ),
    }


# ----------------------------------------------------------------------------- Alertas R1 / R2
def _candidata_alerta(est: Dict[str, Any], estudiante_id: int, parcial_ids: Dict[int, int]) -> Dict[str, Any]:
    unidades = est["promedios_unidad"]
    unidad_critica = min(unidades, key=unidades.get) if unidades else None
    calificadas = [a for a in est["actividades"] if a["nota"] is not None]
    peor = min(calificadas, key=lambda a: a["nota"]) if calificadas else None
    incidencias = [f"{a['id_number']} ({a['estado']})" for a in est["actividades"] if a["estado"] != "CALIFICADO"]
    if est["regla_alerta"] == GradeCalculator.REGLA_R1:
        motivo = f"R1: nota ponderada {est['nota_final']:.2f}/10 (< 5.00)."
    else:
        serie = " -> ".join(f"{u} {v:.2f}" for u, v in unidades.items())
        motivo = (f"R2: descenso entre unidades ({serie}; pendiente {est['pendiente']:+.3f} < -0.25) "
                  f"con nota ponderada {est['nota_final']:.2f}/10 (< 7.00).")
    if incidencias:
        motivo += " Incidencias: " + ", ".join(incidencias) + "."
    return {
        "estudiante_id": estudiante_id,
        "parcial_id": parcial_ids[est["parcial_vigente"]],
        "regla": est["regla_alerta"],
        "nivel": est["nivel_riesgo"],
        "motivo": motivo,
        "unidad_critica": f"Unidad {unidad_critica[1:]}" if unidad_critica else None,
        "tema_critico": f"{peor['id_number']} - {peor['nombre']}"[:80] if peor else None,
        "nota_final": est["nota_final"],
        "pendiente": est["pendiente"],
    }


def persistir(cursos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Guarda la sincronización y regenera las alertas R1/R2 de cada curso."""
    resultado = repositories.persist_sync(cursos)
    alertas = {"creadas": 0, "actualizadas": 0, "resueltas": 0}
    for curso in cursos:
        ids = resultado["ids"][curso["id"]]
        candidatas = [
            _candidata_alerta(e, ids["estudiantes"][e["id_number"]], ids["parciales"])
            for e in curso["estudiantes"] if e["regla_alerta"]
        ]
        for k, v in repositories.sync_alertas(ids["materia_id"], candidatas).items():
            alertas[k] += v
    return {
        "motor": database.backend_name(),
        "materias": resultado["materias"],
        "estudiantes": resultado["estudiantes"],
        "calificaciones": resultado["calificaciones"],
        "ponderadas": resultado["ponderadas"],
        "alertas": alertas,
    }


async def sincronizar(client: Optional[MoodleClient] = None) -> Dict[str, Any]:
    """Ejecuta la extracción completa desde Moodle y la persiste. Lanza MoodleError si Moodle falla."""
    client = client or MoodleClient()
    inicio = time.time()

    info = await client.call("core_webservice_get_site_info")
    prefijo = settings.MOODLE_COURSE_PREFIX.upper()
    cursos_moodle = [
        c for c in await client.get_courses()
        if not prefijo or (c.get("idnumber") or c.get("shortname") or "").upper().startswith(prefijo)
    ]

    cursos: List[Dict[str, Any]] = []
    for c in sorted(cursos_moodle, key=lambda x: x["id"]):
        usuarios = await client.get_enrolled_users(c["id"])
        usergrades = {g["userid"]: g.get("gradeitems", []) for g in await client.get_grade_items(c["id"])}
        cursos.append(_construir_curso(c, usuarios, usergrades))

    try:
        persistencia = persistir(cursos)
    except Exception as ex:  # la base no debe impedir mostrar los datos recién extraídos de Moodle
        logger.exception("No se pudo persistir la sincronización")
        persistencia = {"motor": database.backend_name(), "error": f"{ex.__class__.__name__}: {ex}"}

    SYNC_STATE.update({
        "ultima_sincronizacion": datetime.now(timezone.utc).isoformat(),
        "moodle": {"sitio": info.get("sitename"), "version": info.get("release")},
        "cursos": cursos,
        "persistencia": persistencia,
        "duracion_ms": int((time.time() - inicio) * 1000),
    })
    return SYNC_STATE


@database.on_ready
def cargar_desde_bd(engine) -> None:
    """Al arrancar, reconstruye SYNC_STATE desde la base para que el panel sobreviva a un reinicio."""
    cursos = [
        {
            "id": c["id"], "shortname": c["shortname"], "fullname": c["fullname"], "docentes": c["docentes"],
            "estudiantes": sorted((construir_estudiante(u["user"], u["gradeitems"]) for u in c["usuarios"]),
                                  key=lambda e: e["id_number"]),
        }
        for c in repositories.load_sync(engine)
    ]
    if not cursos:
        return
    ultimo = repositories.last_log("SINCRONIZACION", "EXITO", engine) or {}
    SYNC_STATE.update({
        "ultima_sincronizacion": ultimo.get("timestamp"),
        "moodle": (ultimo.get("detalle") or {}).get("moodle"),
        "cursos": cursos,
        "persistencia": {"motor": database.backend_name(), "origen": "restaurado_desde_bd"},
    })
    logger.info("Sincronización restaurada desde la base: %s cursos", len(cursos))
