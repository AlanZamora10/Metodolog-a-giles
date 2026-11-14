"""
Repositorio de datos de EduMonitor AI (Sprint 3).

Todas las lecturas/escrituras de la base analítica pasan por aquí. Las funciones usan el motor
activo de `app.database` (PostgreSQL en Docker, SQLite en memoria en pruebas), por lo que los
routers y servicios no dependen del motor concreto.
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, delete, func, insert, select, update
from sqlalchemy.engine import Connection, Engine

from app.config import settings
from app.database import (
    actividades, alertas_tempranas, calificaciones, calificaciones_ponderadas, categorias_unidad, estudiantes,
    get_engine, logs_sistema, materias, metadata, parciales, periodos, refuerzos, usuarios,
)

COMPONENTE_BD = {"ACD": "AUTONOMO", "TAREAS": "TAREAS", "PAE": "PAE"}
COMPONENTE_APP = {v: k for k, v in COMPONENTE_BD.items()}
PONDERACION = {"ACD": 0.40, "TAREAS": 0.30, "PAE": 0.30}
ESTADOS_ALERTA_EDITABLES = {"ABIERTA", "RESUELTA"}


def ahora() -> datetime:
    """Instante actual en UTC sin zona (DATETIME2 en SQL Server)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


_ahora = ahora


def _iso(valor: Any) -> Optional[str]:
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=timezone.utc)  # las fechas se guardan en UTC
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return valor


def _dict(row) -> Dict[str, Any]:
    return {k: _iso(v) for k, v in row._mapping.items()}


def _engine(engine: Optional[Engine]) -> Engine:
    return engine or get_engine()


# =============================================================================== Usuarios (HU-14)
def user_by_email(email: str, engine: Optional[Engine] = None) -> Optional[Dict[str, Any]]:
    with _engine(engine).connect() as conn:
        row = conn.execute(select(usuarios).where(usuarios.c.email == email.strip().lower())).first()
    return _dict(row) if row else None


def insert_user(datos: Dict[str, Any], engine: Optional[Engine] = None) -> Dict[str, Any]:
    with _engine(engine).begin() as conn:
        nuevo_id = conn.execute(insert(usuarios).values(**datos).returning(usuarios.c.id)).scalar_one()
        return _dict(conn.execute(select(usuarios).where(usuarios.c.id == nuevo_id)).one())


def update_user(user_id: int, datos: Dict[str, Any], engine: Optional[Engine] = None) -> None:
    with _engine(engine).begin() as conn:
        conn.execute(update(usuarios).where(usuarios.c.id == user_id).values(**datos))


def upsert_usuario_moodle(perfil: Dict[str, Any], engine: Optional[Engine] = None) -> Dict[str, Any]:
    """Crea o actualiza el perfil local de un docente autenticado contra Moodle (sin contraseña local)."""
    email = perfil["email"].strip().lower()
    datos = {
        "nombres": perfil["nombres"][:120], "rol": perfil["rol"], "id_number": perfil.get("id_number"),
        "activo": True, "moodle_user_id": perfil.get("moodle_user_id"),
        "moodle_username": perfil.get("moodle_username"), "ultimo_acceso": ahora(),
        "password_hash": "MOODLE",
    }
    with _engine(engine).begin() as conn:
        _upsert(conn, usuarios, {"email": email}, datos)
        return _dict(conn.execute(select(usuarios).where(usuarios.c.email == email)).one())


# =============================================================================== Auditoría (HU-16 / RN-18)
def insert_log(tipo_proceso: str, estado: str, mensaje: str, detalle: Optional[Dict[str, Any]] = None,
               tiempo_ejecucion_ms: Optional[int] = None, engine: Optional[Engine] = None) -> Dict[str, Any]:
    with _engine(engine).begin() as conn:
        nuevo_id = conn.execute(insert(logs_sistema).values(
            timestamp=_ahora(), tipo_proceso=tipo_proceso, estado=estado, mensaje=mensaje,
            detalle=detalle or {}, tiempo_ejecucion_ms=tiempo_ejecucion_ms,
        ).returning(logs_sistema.c.id)).scalar_one()
        return _dict(conn.execute(select(logs_sistema).where(logs_sistema.c.id == nuevo_id)).one())


def list_logs(limit: int = 500, engine: Optional[Engine] = None) -> List[Dict[str, Any]]:
    with _engine(engine).connect() as conn:
        rows = conn.execute(select(logs_sistema).order_by(logs_sistema.c.id.desc()).limit(limit)).all()
    return [_dict(r) for r in reversed(rows)]


def last_log(tipo_proceso: str, estado: str, engine: Optional[Engine] = None) -> Optional[Dict[str, Any]]:
    with _engine(engine).connect() as conn:
        row = conn.execute(
            select(logs_sistema)
            .where(and_(logs_sistema.c.tipo_proceso == tipo_proceso, logs_sistema.c.estado == estado))
            .order_by(logs_sistema.c.id.desc()).limit(1)
        ).first()
    return _dict(row) if row else None


# =============================================================================== Persistencia de la sincronización
def _id_por_clave(conn: Connection, tabla, filtros: Dict[str, Any]) -> Optional[int]:
    cond = and_(*[tabla.c[k] == v for k, v in filtros.items()])
    return conn.execute(select(tabla.c.id).where(cond)).scalar()


def _upsert(conn: Connection, tabla, clave: Dict[str, Any], valores: Dict[str, Any]) -> int:
    """UPSERT portable (PostgreSQL / SQLite) por clave única."""
    existente = _id_por_clave(conn, tabla, clave)
    if existente is not None:
        if valores:
            conn.execute(update(tabla).where(tabla.c.id == existente).values(**valores))
        return existente
    return conn.execute(insert(tabla).values(**clave, **valores).returning(tabla.c.id)).scalar_one()


def _periodo_y_parciales(conn: Connection) -> Dict[int, int]:
    periodo_id = _upsert(conn, periodos, {"codigo": settings.PERIODO_CODIGO}, {
        "nombre": settings.PERIODO_NOMBRE,
        "fecha_inicio": date.fromisoformat(settings.PERIODO_INICIO),
        "fecha_fin": date.fromisoformat(settings.PERIODO_FIN),
    })
    return {
        n: _upsert(conn, parciales, {"periodo_id": periodo_id, "numero_parcial": n}, {"nombre": f"Parcial {n}"})
        for n in (1, 2)
    }


def _upsert_estudiante(conn: Connection, est: Dict[str, Any]) -> int:
    email = (est.get("email") or f"{est['id_number'].lower()}@moodle.local").strip().lower()
    return _upsert(conn, estudiantes, {"id_number": est["id_number"]}, {
        "nombres": est.get("nombres") or est["id_number"], "email": email,
        "moodle_user_id": est.get("moodle_id"), "activo": True,
    })


def persist_sync(cursos: List[Dict[str, Any]], engine: Optional[Engine] = None) -> Dict[str, Any]:
    """
    Guarda (UPSERT, en una sola transacción) el resultado de la sincronización:
    materias, estudiantes, unidades, actividades, calificaciones y calificaciones ponderadas por parcial.
    Devuelve los ids internos necesarios para generar las alertas.
    """
    resumen = {"materias": 0, "estudiantes": 0, "calificaciones": 0, "ponderadas": 0, "ids": {}}
    with _engine(engine).begin() as conn:
        parcial_ids = _periodo_y_parciales(conn)
        for curso in cursos:
            valores_materia = {
                "nombre": (curso.get("fullname") or curso["shortname"])[:150],
                "moodle_course_id": curso["id"],
                "docentes": sorted(set(curso.get("docentes") or [])),
                "activo": True,
            }
            if curso.get("docente_titular"):
                valores_materia["docente_titular"] = curso["docente_titular"][:150]
            materia_id = _upsert(conn, materias, {"codigo": curso["shortname"][:20]}, valores_materia)
            resumen["materias"] += 1
            unidad_ids: Dict[int, int] = {}
            actividad_ids: Dict[str, int] = {}
            curso_ids = {"materia_id": materia_id, "parciales": parcial_ids, "estudiantes": {}}

            for est in curso["estudiantes"]:
                estudiante_id = _upsert_estudiante(conn, est)
                curso_ids["estudiantes"][est["id_number"]] = estudiante_id
                resumen["estudiantes"] += 1

                vigentes = set()
                for act in est.get("actividades", []):
                    unidad = act.get("unidad")
                    if not unidad or not 1 <= unidad <= 4:
                        continue  # categorias_unidad admite Unidad 1..4
                    if unidad not in unidad_ids:
                        unidad_ids[unidad] = _upsert(conn, categorias_unidad,
                                                     {"materia_id": materia_id, "numero_unidad": unidad},
                                                     {"nombre": f"Unidad {unidad}", "titulo": f"Unidad {unidad}"})
                    clave = f"{curso['shortname']}-{act['id_number']}"[:60]
                    if clave not in actividad_ids:
                        actividad_ids[clave] = _upsert(conn, actividades, {"id_number_normalizado": clave}, {
                            "materia_id": materia_id, "parcial_id": parcial_ids[act["parcial"]],
                            "unidad_id": unidad_ids[unidad], "nombre": (act.get("nombre") or act["id_number"])[:180],
                            "tipo_componente": COMPONENTE_BD[act["componente"]],
                            "ponderacion_componente": PONDERACION[act["componente"]],
                            "tema": f"Unidad {unidad}", "nota_maxima": 10.0,
                        })
                    actividad_id = actividad_ids[clave]
                    vigentes.add(actividad_id)
                    _upsert(conn, calificaciones, {"estudiante_id": estudiante_id, "actividad_id": actividad_id}, {
                        "nota": act["nota"], "estado": act["estado"],
                        "entregado": act["estado"] != "SIN_ENTREGA", "fecha_calificacion": _ahora(),
                    })
                    resumen["calificaciones"] += 1

                # Notas que ya no figuran en Moodle (p. ej. calificación eliminada) dejan de existir aquí
                ids_materia = select(actividades.c.id).where(actividades.c.materia_id == materia_id)
                borrar = delete(calificaciones).where(and_(
                    calificaciones.c.estudiante_id == estudiante_id, calificaciones.c.actividad_id.in_(ids_materia)))
                if vigentes:
                    borrar = borrar.where(calificaciones.c.actividad_id.not_in(vigentes))
                conn.execute(borrar)

                for numero, m in est.get("por_parcial", {}).items():
                    _upsert(conn, calificaciones_ponderadas, {
                        "estudiante_id": estudiante_id, "materia_id": materia_id, "parcial_id": parcial_ids[numero],
                    }, {
                        "nota_autonomo": m["acd"] or 0.0, "nota_tareas": m["tareas"] or 0.0, "nota_pae": m["pae"] or 0.0,
                        "nota_final": m["nota_final"], "nivel_riesgo": m["nivel_riesgo"], "tendencia": m["tendencia"],
                        "pendiente_regresion": m["pendiente"], "probabilidad_aprobacion": m["probabilidad_aprobacion"],
                        "updated_at": _ahora(),
                    })
                    resumen["ponderadas"] += 1
            resumen["ids"][curso["id"]] = curso_ids
    return resumen


def load_sync(engine: Optional[Engine] = None) -> List[Dict[str, Any]]:
    """
    Reconstruye la última sincronización desde la base (cursos de Moodle, matrícula y notas por actividad)
    en el mismo formato de entrada que entrega Moodle, para que sync_service recalcule las métricas.
    """
    cursos: List[Dict[str, Any]] = []
    with _engine(engine).connect() as conn:
        filas_materias = conn.execute(
            select(materias).where(materias.c.moodle_course_id.is_not(None)).order_by(materias.c.moodle_course_id)
        ).all()
        for m in filas_materias:
            matriculados = conn.execute(
                select(estudiantes).distinct()
                .join(calificaciones_ponderadas, calificaciones_ponderadas.c.estudiante_id == estudiantes.c.id)
                .where(calificaciones_ponderadas.c.materia_id == m.id)
            ).all()
            notas = conn.execute(
                select(calificaciones.c.estudiante_id, calificaciones.c.nota, calificaciones.c.estado,
                       actividades.c.id_number_normalizado, actividades.c.nombre)
                .join(actividades, actividades.c.id == calificaciones.c.actividad_id)
                .where(actividades.c.materia_id == m.id)
            ).all()
            prefijo = f"{m.codigo}-"
            items: Dict[int, List[Dict[str, Any]]] = {}
            for n in notas:
                feedback = {"SIN_ENTREGA": "SIN ENTREGA", "PENDIENTE": "PENDIENTE"}.get(n.estado or "", "")
                items.setdefault(n.estudiante_id, []).append({
                    "idnumber": n.id_number_normalizado[len(prefijo):] if n.id_number_normalizado.startswith(prefijo)
                    else n.id_number_normalizado,
                    "itemname": n.nombre, "graderaw": n.nota, "grademax": 10, "feedback": feedback,
                })
            cursos.append({
                "id": m.moodle_course_id, "shortname": m.codigo, "fullname": m.nombre,
                "docentes": list(m.docentes or []),
                "usuarios": [{
                    "user": {"id": e.moodle_user_id, "fullname": e.nombres, "idnumber": e.id_number, "email": e.email},
                    "gradeitems": items.get(e.id, []),
                } for e in matriculados],
            })
    return cursos


# =============================================================================== Alertas tempranas (R1 / R2)
def sync_alertas(materia_id: int, candidatas: List[Dict[str, Any]], engine: Optional[Engine] = None) -> Dict[str, int]:
    """
    Crea o actualiza las alertas R1/R2 de una materia tras sincronizar.
    - Alerta nueva -> ABIERTA.  Alerta ABIERTA/RESUELTA que sigue vigente -> se actualiza (y se reabre).
    - ATENDIDA / PUBLICADO / CERRADA no se modifican (ciclo de vida RN-14).
    - ABIERTA cuyo estudiante ya no cumple la regla -> RESUELTA (resuelto = true).
    """
    conteo = {"creadas": 0, "actualizadas": 0, "resueltas": 0}
    ahora = _ahora()
    with _engine(engine).begin() as conn:
        existentes = {
            (r.estudiante_id, r.parcial_id, r.regla): r
            for r in conn.execute(select(alertas_tempranas).where(and_(
                alertas_tempranas.c.materia_id == materia_id, alertas_tempranas.c.regla.is_not(None)))).all()
        }
        vigentes = set()
        for c in candidatas:
            clave = (c["estudiante_id"], c["parcial_id"], c["regla"])
            vigentes.add(clave)
            datos = {
                "nivel": c["nivel"], "motivo": c["motivo"], "unidad_critica": c.get("unidad_critica"),
                "tema_critico": c.get("tema_critico"), "nota_final": c["nota_final"], "pendiente": c["pendiente"],
                "fecha_actualizacion": ahora,
            }
            actual = existentes.get(clave)
            if actual is None:
                conn.execute(insert(alertas_tempranas).values(
                    estudiante_id=c["estudiante_id"], materia_id=materia_id, parcial_id=c["parcial_id"],
                    regla=c["regla"], estado="ABIERTA", resuelto=False, fecha_alerta=ahora, **datos))
                conteo["creadas"] += 1
            elif actual.estado in ESTADOS_ALERTA_EDITABLES:
                conn.execute(update(alertas_tempranas).where(alertas_tempranas.c.id == actual.id).values(
                    estado="ABIERTA", resuelto=False, fecha_resolucion=None, **datos))
                conteo["actualizadas"] += 1
        for clave, r in existentes.items():
            if clave not in vigentes and r.estado == "ABIERTA":
                conn.execute(update(alertas_tempranas).where(alertas_tempranas.c.id == r.id).values(
                    estado="RESUELTA", resuelto=True, fecha_resolucion=ahora, fecha_actualizacion=ahora))
                conteo["resueltas"] += 1
    return conteo


def _consulta_alertas():
    return (
        select(
            alertas_tempranas,
            materias.c.codigo.label("curso_codigo"), materias.c.nombre.label("curso_nombre"),
            materias.c.moodle_course_id.label("curso_id"), materias.c.docentes.label("curso_docentes"),
            estudiantes.c.id_number, estudiantes.c.nombres, estudiantes.c.email,
            parciales.c.numero_parcial, refuerzos.c.id.label("refuerzo_id"),
        )
        .join(materias, materias.c.id == alertas_tempranas.c.materia_id)
        .join(estudiantes, estudiantes.c.id == alertas_tempranas.c.estudiante_id)
        .join(parciales, parciales.c.id == alertas_tempranas.c.parcial_id)
        .outerjoin(refuerzos, refuerzos.c.alerta_id == alertas_tempranas.c.id)
    )


def list_alertas(course_id: Optional[int] = None, estado: Optional[str] = None,
                 engine: Optional[Engine] = None) -> List[Dict[str, Any]]:
    q = _consulta_alertas().where(alertas_tempranas.c.regla.is_not(None))
    if course_id is not None:
        q = q.where(materias.c.moodle_course_id == course_id)
    if estado:
        q = q.where(alertas_tempranas.c.estado == estado.upper())
    with _engine(engine).connect() as conn:
        rows = conn.execute(q.order_by(alertas_tempranas.c.nota_final, alertas_tempranas.c.id)).all()
    return [_dict(r) for r in rows]


def get_alerta(alerta_id: int, engine: Optional[Engine] = None) -> Optional[Dict[str, Any]]:
    with _engine(engine).connect() as conn:
        row = conn.execute(_consulta_alertas().where(alertas_tempranas.c.id == alerta_id)).first()
    return _dict(row) if row else None


def update_alerta(alerta_id: int, datos: Dict[str, Any], engine: Optional[Engine] = None) -> None:
    with _engine(engine).begin() as conn:
        conn.execute(update(alertas_tempranas).where(alertas_tempranas.c.id == alerta_id)
                     .values(fecha_actualizacion=_ahora(), **datos))


def notas_actividades(estudiante_id: int, materia_id: int, engine: Optional[Engine] = None) -> List[Tuple[str, float]]:
    """(id_number_normalizado, nota) de las actividades calificadas del estudiante en la materia."""
    with _engine(engine).connect() as conn:
        rows = conn.execute(
            select(actividades.c.id_number_normalizado, calificaciones.c.nota)
            .join(actividades, actividades.c.id == calificaciones.c.actividad_id)
            .where(and_(calificaciones.c.estudiante_id == estudiante_id, actividades.c.materia_id == materia_id,
                        calificaciones.c.nota.is_not(None)))
            .order_by(actividades.c.id_number_normalizado)
        ).all()
    return [(r.id_number_normalizado, float(r.nota)) for r in rows]


# =============================================================================== Refuerzos (tabla 12)
def get_refuerzo(refuerzo_id: Optional[int] = None, alerta_id: Optional[int] = None,
                 engine: Optional[Engine] = None) -> Optional[Dict[str, Any]]:
    cond = refuerzos.c.id == refuerzo_id if refuerzo_id is not None else refuerzos.c.alerta_id == alerta_id
    with _engine(engine).connect() as conn:
        row = conn.execute(select(refuerzos).where(cond)).first()
    return _dict(row) if row else None


def upsert_refuerzo(alerta_id: int, datos: Dict[str, Any], engine: Optional[Engine] = None) -> Dict[str, Any]:
    with _engine(engine).begin() as conn:
        refuerzo_id = _upsert(conn, refuerzos, {"alerta_id": alerta_id}, datos)
        return _dict(conn.execute(select(refuerzos).where(refuerzos.c.id == refuerzo_id)).one())


def update_refuerzo(refuerzo_id: int, datos: Dict[str, Any], engine: Optional[Engine] = None) -> Dict[str, Any]:
    with _engine(engine).begin() as conn:
        conn.execute(update(refuerzos).where(refuerzos.c.id == refuerzo_id).values(**datos))
        return _dict(conn.execute(select(refuerzos).where(refuerzos.c.id == refuerzo_id)).one())


def contar(tabla_nombre: str, engine: Optional[Engine] = None) -> int:
    """Utilidad de diagnóstico/pruebas: número de filas de una tabla del esquema."""
    with _engine(engine).connect() as conn:
        return conn.execute(select(func.count()).select_from(metadata.tables[tabla_nombre])).scalar_one()


def filas(tabla_nombre: str, engine: Optional[Engine] = None) -> List[Dict[str, Any]]:
    with _engine(engine).connect() as conn:
        return [_dict(r) for r in conn.execute(select(metadata.tables[tabla_nombre])).all()]
