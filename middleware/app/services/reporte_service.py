"""
Reporte / informe de un curso (Fase A, consumido por el frontend React).

Todo se calcula de forma determinista a partir de la última sincronización con Moodle (persistida en la
base) y de las alertas R1/R2 registradas: período, métricas, distribución de estados de las actividades
(cero, sin entrega, pendiente), hallazgos, recomendaciones y fecha de sincronización. No hay texto generado
por IA: cada hallazgo cita los datos que lo sustentan.
"""

import statistics
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings

COMPONENTES = {"acd": "ACD (40%)", "tareas": "Tareas (30%)", "pae": "PAE (30%)"}
_RECOMENDACION_COMPONENTE = {
    "acd": "Reforzar las evaluaciones en contacto con el docente (ACD) con repasos guiados antes de cada evaluación.",
    "tareas": "Revisar la carga y las instrucciones de las tareas autónomas; habilitar asesorías para su desarrollo.",
    "pae": "Acompañar las prácticas de aplicación (PAE) con laboratorios guiados y retroalimentación temprana.",
}


def _prom(valores: List[float]) -> Optional[float]:
    return round(sum(valores) / len(valores), 2) if valores else None


def _nombre(e: Dict[str, Any]) -> str:
    return e.get("nombres") or e["id_number"]


def construir_reporte(curso: Dict[str, Any], alertas: List[Dict[str, Any]],
                      ultima_sincronizacion: Optional[str]) -> Dict[str, Any]:
    est = curso["estudiantes"]
    notas = [e["nota_final"] for e in est]
    total = len(est)

    # ------------------------------------------------------------------ Métricas
    niveles = Counter(e["nivel_riesgo"] for e in est)
    componentes = {k: _prom([e[k] for e in est if e.get(k) is not None]) for k in COMPONENTES}
    por_unidad: Dict[str, List[float]] = {}
    for e in est:
        for unidad, valor in (e.get("promedios_unidad") or {}).items():
            if valor is not None:
                por_unidad.setdefault(unidad, []).append(valor)
    unidades = {u: _prom(v) for u, v in sorted(por_unidad.items(), key=lambda x: int(x[0][1:]))}
    metricas = {
        "total_estudiantes": total,
        "promedio": _prom(notas) or 0.0,
        "mediana": round(statistics.median(notas), 2) if notas else 0.0,
        "nota_minima": min(notas) if notas else 0.0,
        "nota_maxima": max(notas) if notas else 0.0,
        "desviacion_estandar": round(statistics.pstdev(notas), 2) if total > 1 else 0.0,
        "criticos": niveles.get("CRITICO", 0),
        "en_riesgo": niveles.get("EN_RIESGO", 0),
        "aceptables": niveles.get("ACEPTABLE", 0),
        "porcentaje_aceptables": round(100 * niveles.get("ACEPTABLE", 0) / total, 1) if total else 0.0,
        "componentes": componentes,
        "promedio_por_unidad": unidades,
    }

    # ------------------------------------------------------------------ Distribución de estados (actividades)
    conteo = Counter()
    estudiantes_por_estado: Dict[str, set] = {"cero": set(), "sin_entrega": set(), "pendiente": set()}
    incidencias_actividad: Counter = Counter()
    for e in est:
        for a in e.get("actividades", []):
            if a["estado"] == "SIN_ENTREGA":
                clave = "sin_entrega"
            elif a["estado"] == "PENDIENTE":
                clave = "pendiente"
            elif a["nota"] == 0:
                clave = "cero"
            else:
                clave = "calificado"
            conteo[clave] += 1
            if clave != "calificado":
                estudiantes_por_estado[clave].add(e["id_number"])
                if clave in ("cero", "sin_entrega"):
                    incidencias_actividad[a["id_number"]] += 1
    distribucion = {
        "calificado": conteo["calificado"], "cero": conteo["cero"], "sin_entrega": conteo["sin_entrega"],
        "pendiente": conteo["pendiente"], "total_registros": sum(conteo.values()),
        "estudiantes_con_cero": len(estudiantes_por_estado["cero"]),
        "estudiantes_sin_entrega": len(estudiantes_por_estado["sin_entrega"]),
        "estudiantes_con_pendiente": len(estudiantes_por_estado["pendiente"]),
    }

    # ------------------------------------------------------------------ Alertas
    estados_alerta = Counter(a["estado"] for a in alertas)
    reglas = Counter(a["regla"] for a in alertas if a["estado"] not in ("RESUELTA", "CERRADA"))
    resumen_alertas = {
        "r1_activas": reglas.get("R1_NOTA_CRITICA", 0), "r2_activas": reglas.get("R2_DESCENSO", 0),
        "abiertas": estados_alerta.get("ABIERTA", 0), "atendidas": estados_alerta.get("ATENDIDA", 0),
        "publicadas": estados_alerta.get("PUBLICADO", 0), "cerradas": estados_alerta.get("CERRADA", 0),
        "resueltas": estados_alerta.get("RESUELTA", 0),
    }
    prioritarios = [
        {"id_number": e["id_number"], "nombres": _nombre(e), "nota_final": e["nota_final"],
         "nivel_riesgo": e["nivel_riesgo"], "regla_alerta": e.get("regla_alerta")}
        for e in sorted(est, key=lambda x: x["nota_final"]) if e.get("regla_alerta")
    ]

    # ------------------------------------------------------------------ Hallazgos (cada uno cita sus datos)
    hallazgos: List[str] = []
    if total:
        hallazgos.append(
            f"Promedio del curso {metricas['promedio']:.2f}/10 (mediana {metricas['mediana']:.2f}); "
            f"{metricas['aceptables']} de {total} estudiantes ({metricas['porcentaje_aceptables']}%) en nivel aceptable.")
    if metricas["criticos"]:
        criticos = [p for p in prioritarios if p["nivel_riesgo"] == "CRITICO"]
        hallazgos.append(f"{metricas['criticos']} estudiante(s) en nivel crítico (< 5.00): "
                         + ", ".join(f"{p['nombres']} ({p['nota_final']:.2f})" for p in criticos) + ".")
    comp_validos = {k: v for k, v in componentes.items() if v is not None}
    comp_bajo = min(comp_validos, key=comp_validos.get) if comp_validos else None
    if comp_bajo:
        hallazgos.append(f"El componente con menor promedio es {COMPONENTES[comp_bajo]}: {comp_validos[comp_bajo]:.2f}/10.")
    if len(unidades) >= 2:
        serie = list(unidades.items())
        (u_ini, v_ini), (u_fin, v_fin) = serie[0], serie[-1]
        tendencia = "baja" if v_fin < v_ini else "sube" if v_fin > v_ini else "se mantiene"
        hallazgos.append(f"El promedio por unidad {tendencia} de {u_ini} ({v_ini:.2f}) a {u_fin} ({v_fin:.2f}).")
    if resumen_alertas["r2_activas"]:
        nombres_r2 = [p["nombres"] for p in prioritarios if p["regla_alerta"] == "R2_DESCENSO"]
        hallazgos.append(f"{resumen_alertas['r2_activas']} estudiante(s) con descenso sostenido entre unidades (R2): "
                         + ", ".join(nombres_r2) + ".")
    if incidencias_actividad:
        actividad, veces = incidencias_actividad.most_common(1)[0]
        hallazgos.append(f"La actividad {actividad} concentra {veces} registro(s) con nota 0 o sin entrega.")
    if distribucion["pendiente"]:
        hallazgos.append(f"{distribucion['pendiente']} actividad(es) siguen pendientes de revisión "
                         f"({distribucion['estudiantes_con_pendiente']} estudiante(s)); no cuentan en el promedio.")

    # ------------------------------------------------------------------ Recomendaciones (reglas sobre los datos)
    recomendaciones: List[str] = []
    if metricas["criticos"]:
        recomendaciones.append("Atender primero las alertas R1 desde el Centro de Alertas y publicar un refuerzo "
                               "personalizado en Moodle para cada estudiante crítico.")
    if resumen_alertas["r2_activas"]:
        unidad_baja = min(unidades, key=unidades.get) if unidades else "la última unidad"
        recomendaciones.append(f"Revisar los contenidos de {unidad_baja} con los estudiantes en descenso (R2) "
                               "antes de que su nota baje de 5.00.")
    if comp_bajo and comp_validos[comp_bajo] < 7:
        recomendaciones.append(_RECOMENDACION_COMPONENTE[comp_bajo])
    if distribucion["sin_entrega"] or distribucion["cero"]:
        recomendaciones.append("Contactar a los estudiantes con entregas faltantes o nota 0 y, si procede, "
                               "habilitar una segunda oportunidad de entrega.")
    if distribucion["pendiente"]:
        recomendaciones.append(f"Calificar las {distribucion['pendiente']} actividad(es) pendientes y volver a "
                               "sincronizar para completar el análisis.")
    if not recomendaciones:
        recomendaciones.append("Mantener el seguimiento semanal: no hay estudiantes en riesgo ni incidencias registradas.")

    return {
        "curso": {"id": curso["id"], "shortname": curso["shortname"], "fullname": curso["fullname"],
                  "docentes": curso.get("docentes", [])},
        "periodo": {"codigo": settings.PERIODO_CODIGO, "nombre": settings.PERIODO_NOMBRE,
                    "inicio": settings.PERIODO_INICIO, "fin": settings.PERIODO_FIN},
        "fecha_sincronizacion": ultima_sincronizacion,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "metricas": metricas,
        "distribucion_estados": distribucion,
        "alertas": resumen_alertas,
        "estudiantes_prioritarios": prioritarios,
        "hallazgos": hallazgos,
        "recomendaciones": recomendaciones,
    }


def reporte_markdown(r: Dict[str, Any]) -> str:
    """Versión descargable (Markdown) del reporte."""
    m, d, a = r["metricas"], r["distribucion_estados"], r["alertas"]
    comp = m["componentes"]
    fmt = lambda v: "—" if v is None else f"{v:.2f}"  # noqa: E731
    lineas = [
        f"# Informe del curso {r['curso']['shortname']}",
        f"**{r['curso']['fullname']}**  ",
        f"Período: {r['periodo']['nombre']} ({r['periodo']['inicio']} a {r['periodo']['fin']})  ",
        f"Última sincronización con Moodle: {r['fecha_sincronizacion'] or 'sin datos'}  ",
        f"Generado: {r['generado_en']}",
        "",
        "## Métricas",
        "| Indicador | Valor |", "|---|---|",
        f"| Estudiantes | {m['total_estudiantes']} |",
        f"| Promedio / mediana | {m['promedio']:.2f} / {m['mediana']:.2f} |",
        f"| Mínima / máxima | {m['nota_minima']:.2f} / {m['nota_maxima']:.2f} |",
        f"| Críticos / en riesgo / aceptables | {m['criticos']} / {m['en_riesgo']} / {m['aceptables']} |",
        f"| ACD / Tareas / PAE | {fmt(comp['acd'])} / {fmt(comp['tareas'])} / {fmt(comp['pae'])} |",
        "",
        "## Distribución de estados de las actividades",
        "| Estado | Registros | Estudiantes |", "|---|---|---|",
        f"| Calificado | {d['calificado']} | — |",
        f"| Nota 0 | {d['cero']} | {d['estudiantes_con_cero']} |",
        f"| Sin entrega | {d['sin_entrega']} | {d['estudiantes_sin_entrega']} |",
        f"| Pendiente de revisión | {d['pendiente']} | {d['estudiantes_con_pendiente']} |",
        "",
        "## Alertas",
        f"R1 activas: {a['r1_activas']} · R2 activas: {a['r2_activas']} · abiertas {a['abiertas']}, "
        f"atendidas {a['atendidas']}, publicadas {a['publicadas']}, cerradas {a['cerradas']}, resueltas {a['resueltas']}.",
        "",
        "## Hallazgos",
        *[f"- {h}" for h in r["hallazgos"]],
        "",
        "## Recomendaciones",
        *[f"- {x}" for x in r["recomendaciones"]],
        "",
    ]
    return "\n".join(lineas)
