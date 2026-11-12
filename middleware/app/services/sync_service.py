"""
Servicio de sincronización Moodle UTA -> EduMonitor AI.

Extrae los cursos del portafolio, TODOS sus docentes/estudiantes matriculados y el libro
de calificaciones, calcula la nota ponderada y el nivel de riesgo, y deja el resultado en
memoria (SYNC_STATE).

Las actividades se clasifican por su ID number institucional:
  Ux-Ay -> ACD (40%)   Ux-Ty -> Tareas (30%)   Ux-Py -> PAE (30%)
Cada componente es el promedio (sobre 10) de sus actividades calificadas:
  - nota numérica                 -> cuenta (incluye 0)
  - sin nota + "SIN ENTREGA"      -> cuenta como 0
  - sin nota + "PENDIENTE"        -> no cuenta (pendiente de revisión)
  - sin nota y sin comentario     -> no cuenta (aún no evaluada)
"""

import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.services.grade_calculator import GradeCalculator
from app.services.moodle_client import MoodleClient

TEACHER_ROLES = {"editingteacher", "teacher"}
STUDENT_ROLES = {"student"}
COMPONENTES = ("ACD", "TAREAS", "PAE")
_PATRON_ACTIVIDAD = re.compile(r"^U(\d+)-([ATP])(\d+)$", re.IGNORECASE)
_LETRA_COMPONENTE = {"A": "ACD", "T": "TAREAS", "P": "PAE"}
_PRIORIDAD_ESTADO = {"CALIFICADO": 0, "PENDIENTE": 1, "SIN_ENTREGA": 2}

# Último resultado de sincronización (en memoria)
SYNC_STATE: Dict[str, Any] = {"ultima_sincronizacion": None, "moodle": None, "cursos": []}


def _roles(user: Dict[str, Any]) -> set:
    return {r.get("shortname") for r in user.get("roles", [])}


def _componente(item: Dict[str, Any]) -> Optional[str]:
    match = _PATRON_ACTIVIDAD.match((item.get("idnumber") or "").strip())
    return _LETRA_COMPONENTE[match.group(2).upper()] if match else None


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


def construir_estudiante(user: Dict[str, Any], gradeitems: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convierte un usuario de Moodle + sus ítems de calificación en el registro analítico."""
    valores: Dict[str, List[float]] = {c: [] for c in COMPONENTES}
    estados: Dict[str, str] = {}
    actividades: List[Dict[str, Any]] = []

    for item in gradeitems:
        comp = _componente(item)
        if not comp:
            continue
        estado, nota = _estado_actividad(item)
        if estado == "NO_EVALUADA":
            continue
        actividades.append({
            "id_number": item.get("idnumber"),
            "nombre": item.get("itemname"),
            "componente": comp,
            "nota": nota,
            "estado": estado,
        })
        if nota is not None:
            valores[comp].append(nota)
        # El estado del componente refleja la incidencia más relevante: SIN_ENTREGA > PENDIENTE > CALIFICADO
        if _PRIORIDAD_ESTADO[estado] >= _PRIORIDAD_ESTADO[estados.get(comp, "CALIFICADO")]:
            estados[comp] = estado

    promedios = {c: (round(sum(v) / len(v), 2) if v else None) for c, v in valores.items()}
    # Un componente sin ninguna actividad que cuente aporta 0.00 a la nota ponderada.
    nota_final = GradeCalculator.calculate_weighted_grade(
        autonomo=promedios["ACD"] or 0.0,
        tareas=promedios["TAREAS"] or 0.0,
        pae=promedios["PAE"] or 0.0,
    )
    return {
        "moodle_id": user.get("id"),
        "id_number": user.get("idnumber") or f"MDL-{user.get('id')}",
        "nombres": user.get("fullname"),
        "email": user.get("email"),
        "acd": promedios["ACD"],
        "tareas": promedios["TAREAS"],
        "pae": promedios["PAE"],
        "estados": estados,
        "actividades": sorted(actividades, key=lambda a: a["id_number"]),
        "nota_final": nota_final,
        "nivel_riesgo": GradeCalculator.classify_risk(nota_final),
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
        "total_cursos": len(cursos),
        "total_estudiantes": len(estudiantes),
        "cursos": [resumen_curso(c) for c in cursos],
        "estudiantes": sorted(estudiantes.values(), key=lambda e: e["id_number"]),
    }


async def sincronizar(client: Optional[MoodleClient] = None) -> Dict[str, Any]:
    """Ejecuta la extracción completa desde Moodle. Lanza MoodleError si falla."""
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
        docentes = [u for u in usuarios if _roles(u) & TEACHER_ROLES]
        alumnos = [u for u in usuarios if _roles(u) & STUDENT_ROLES]
        cursos.append({
            "id": c["id"],
            "shortname": c.get("shortname"),
            "fullname": c.get("fullname"),
            "docentes": [(u.get("email") or "").lower() for u in docentes],
            "estudiantes": sorted(
                (construir_estudiante(u, usergrades.get(u["id"], [])) for u in alumnos),
                key=lambda e: e["id_number"],
            ),
        })

    SYNC_STATE.update({
        "ultima_sincronizacion": datetime.now(timezone.utc).isoformat(),
        "moodle": {"sitio": info.get("sitename"), "version": info.get("release")},
        "cursos": cursos,
        "duracion_ms": int((time.time() - inicio) * 1000),
    })
    return SYNC_STATE
