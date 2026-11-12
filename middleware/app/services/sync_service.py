"""
Servicio de sincronización Moodle UTA -> EduMonitor AI.

Extrae los cursos del portafolio, sus docentes/estudiantes matriculados y el libro
de calificaciones (componentes AUTONOMO 40% / TAREAS 30% / PAE 30%), calcula la nota
ponderada y el nivel de riesgo, y deja el resultado en memoria (SYNC_STATE).
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.grade_calculator import GradeCalculator
from app.services.moodle_client import MoodleClient

TEACHER_ROLES = {"editingteacher", "teacher"}
STUDENT_ROLES = {"student"}
COMPONENTES = ("AUTONOMO", "TAREAS", "PAE")

# Último resultado de sincronización (en memoria)
SYNC_STATE: Dict[str, Any] = {"ultima_sincronizacion": None, "moodle": None, "cursos": []}


def _roles(user: Dict[str, Any]) -> set:
    return {r.get("shortname") for r in user.get("roles", [])}


def _componente(item: Dict[str, Any]) -> Optional[str]:
    idnumber = (item.get("idnumber") or "").upper()
    for comp in COMPONENTES:
        if idnumber.endswith(f"-{comp}"):
            return comp
    return None


def construir_estudiante(user: Dict[str, Any], gradeitems: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convierte un usuario de Moodle + sus ítems de calificación en el registro analítico."""
    notas: Dict[str, Optional[float]] = {c: None for c in COMPONENTES}
    estados: Dict[str, str] = {}
    for item in gradeitems:
        comp = _componente(item)
        if not comp:
            continue
        raw = item.get("graderaw")
        if raw is not None:
            notas[comp] = round(float(raw), 2)
            estados[comp] = "CALIFICADO"
        elif "PENDIENTE" in (item.get("feedback") or "").upper():
            estados[comp] = "PENDIENTE"
        else:
            estados[comp] = "SIN_ENTREGA"

    # Un componente sin nota (SIN_ENTREGA / PENDIENTE) cuenta como 0.00 en el cálculo.
    nota_final = GradeCalculator.calculate_weighted_grade(
        autonomo=notas["AUTONOMO"] or 0.0,
        tareas=notas["TAREAS"] or 0.0,
        pae=notas["PAE"] or 0.0,
    )
    return {
        "moodle_id": user.get("id"),
        "id_number": user.get("idnumber") or f"MDL-{user.get('id')}",
        "nombres": user.get("fullname"),
        "email": user.get("email"),
        "autonomo": notas["AUTONOMO"],
        "tareas": notas["TAREAS"],
        "pae": notas["PAE"],
        "estados": estados,
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
