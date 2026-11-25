"""
Reporte / informe de un curso (Fase A, consumido por el frontend React).

Todo se calcula de forma determinista a partir de la última sincronización con Moodle (persistida en la
base) y de las alertas R1/R2 registradas: período, métricas, distribución de estados de las actividades
(cero, sin entrega, pendiente), hallazgos, recomendaciones y fecha de sincronización. No hay texto generado
por IA: cada hallazgo cita los datos que lo sustentan.
"""

import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.config import settings

COMPONENTES = {"acd": "Exámenes (40%)", "tareas": "Tareas (30%)", "pae": "APE (30%)"}
_RECOMENDACION_COMPONENTE = {
    "acd": "Reforzar la preparación de los exámenes con repasos guiados antes de cada evaluación.",
    "tareas": "Revisar la carga y las instrucciones de las tareas autónomas; habilitar asesorías para su desarrollo.",
    "pae": "Acompañar el aprendizaje práctico experimental (APE) con laboratorios guiados y retroalimentación temprana.",
}


def _prom(valores: List[float]) -> Optional[float]:
    return round(sum(valores) / len(valores), 2) if valores else None


def _nombre(e: Dict[str, Any]) -> str:
    return e.get("nombres") or e["id_number"]


def plural(cantidad: int, singular: str, plural_: str) -> str:
    """plural(1, 'estudiante', 'estudiantes') -> '1 estudiante'; con 2 -> '2 estudiantes' (sin «estudiante(s)»)."""
    return f"{cantidad} {singular if cantidad == 1 else plural_}"


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
    # Tres bloques ordenados: rendimiento general, estudiantes que requieren atención, componentes y entregas.
    rendimiento: List[str] = []
    if total:
        rendimiento.append(f"Promedio general {metricas['promedio']:.2f}/10 y mediana {metricas['mediana']:.2f}.")
        aceptables = metricas["aceptables"]
        rendimiento.append(f"{aceptables} de {plural(total, 'estudiante', 'estudiantes')} "
                           f"({metricas['porcentaje_aceptables']:.1f} %) {'está' if aceptables == 1 else 'están'} "
                           "en nivel aceptable.")
    if len(unidades) >= 2:
        serie = list(unidades.items())
        (u_ini, v_ini), (u_fin, v_fin) = serie[0], serie[-1]
        tendencia = "baja" if v_fin < v_ini else "sube" if v_fin > v_ini else "se mantiene"
        rendimiento.append(f"El promedio por unidad {tendencia} de Unidad {u_ini[1:]} ({v_ini:.2f}) a "
                           f"Unidad {u_fin[1:]} ({v_fin:.2f}).")

    atencion: List[str] = []
    criticos = [p for p in prioritarios if p["nivel_riesgo"] == "CRITICO"]
    if metricas["criticos"]:
        detalle = (": " + ", ".join(f"{p['nombres']} ({p['nota_final']:.2f})" for p in criticos)) if criticos else ""
        atencion.append(f"{plural(metricas['criticos'], 'estudiante', 'estudiantes')} en nivel crítico{detalle}.")
    if resumen_alertas["r2_activas"]:
        nombres_r2 = [p["nombres"] for p in prioritarios if p["regla_alerta"] == "R2_DESCENSO"]
        atencion.append(f"{plural(resumen_alertas['r2_activas'], 'estudiante', 'estudiantes')} con descenso sostenido "
                        "entre unidades" + (f": {', '.join(nombres_r2)}." if nombres_r2 else "."))
    if not atencion:
        atencion.append("Ningún estudiante en nivel crítico ni con descenso sostenido entre unidades.")

    entregas: List[str] = []
    comp_validos = {k: v for k, v in componentes.items() if v is not None}
    comp_bajo = min(comp_validos, key=comp_validos.get) if comp_validos else None
    if comp_bajo:
        entregas.append(f"El componente con menor promedio es {COMPONENTES[comp_bajo]}: {comp_validos[comp_bajo]:.2f}/10.")
    if incidencias_actividad:
        actividad, veces = incidencias_actividad.most_common(1)[0]
        entregas.append(f"La actividad {actividad} concentra {plural(veces, 'registro', 'registros')} con nota 0 o "
                        "sin entrega.")
    if distribucion["pendiente"]:
        n = distribucion["pendiente"]
        entregas.append(f"{plural(n, 'actividad sigue pendiente', 'actividades siguen pendientes')} de calificación "
                        f"({plural(distribucion['estudiantes_con_pendiente'], 'estudiante', 'estudiantes')}); "
                        f"{'no cuenta' if n == 1 else 'no cuentan'} en el promedio.")
    if not entregas:
        entregas.append("No hay actividades con nota 0, sin entrega ni pendientes de calificación.")

    hallazgos_grupos = [
        {"titulo": "Rendimiento general del curso", "items": rendimiento},
        {"titulo": "Estudiantes que requieren atención", "items": atencion},
        {"titulo": "Componentes y entregas pendientes", "items": entregas},
    ]
    hallazgos = [h for g in hallazgos_grupos for h in g["items"]]

    # ------------------------------------------------------------------ Recomendaciones (en orden de prioridad)
    recomendaciones: List[str] = []
    if metricas["criticos"]:
        recomendaciones.append(
            f"Atención inmediata a {plural(metricas['criticos'], 'estudiante crítico', 'estudiantes críticos')}: "
            "atender sus alertas desde el Centro de alertas y publicar un refuerzo personalizado en Moodle.")
    if resumen_alertas["r2_activas"]:
        unidad_baja = min(unidades, key=unidades.get) if unidades else None
        recomendaciones.append(
            f"Seguimiento al descenso sostenido de "
            f"{plural(resumen_alertas['r2_activas'], 'estudiante', 'estudiantes')}: revisar los contenidos de "
            f"{('la Unidad ' + unidad_baja[1:]) if unidad_baja else 'la última unidad'} antes de que su nota baje de 5.00.")
    if comp_bajo and comp_validos[comp_bajo] < 7:
        texto = _RECOMENDACION_COMPONENTE[comp_bajo]
        recomendaciones.append(f"Refuerzo del componente {COMPONENTES[comp_bajo]}: {texto[:1].lower()}{texto[1:]}")
    if distribucion["sin_entrega"] or distribucion["cero"]:
        faltantes = distribucion["sin_entrega"] + distribucion["cero"]
        recomendaciones.append(
            f"Gestión de entregas faltantes ({plural(faltantes, 'registro', 'registros')} con nota 0 o sin entrega): "
            "contactar a los estudiantes y, si procede, habilitar una segunda oportunidad de entrega.")
    if distribucion["pendiente"]:
        n = distribucion["pendiente"]
        recomendaciones.append(
            f"Calificación de pendientes: calificar {'la actividad pendiente' if n == 1 else f'las {n} actividades pendientes'} "
            "y volver a sincronizar para completar el análisis.")
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
        "hallazgos_grupos": hallazgos_grupos,
        "recomendaciones": recomendaciones,
    }


_ECUADOR = timezone(timedelta(hours=-5))
_NIVEL = {"CRITICO": "Crítico", "EN_RIESGO": "En riesgo", "ACEPTABLE": "Aceptable"}
_ALERTA = {"R1_NOTA_CRITICA": "Nota crítica", "R2_DESCENSO": "Descenso sostenido"}


def _fecha_hora(valor: Optional[str]) -> str:
    """ISO (UTC) -> '25/11/2026 14:16' en hora de Ecuador."""
    if not valor:
        return "Sin sincronizar"
    try:
        fecha = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return str(valor)
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(_ECUADOR).strftime("%d/%m/%Y %H:%M")


def _fecha(valor: Optional[str]) -> str:
    try:
        return datetime.fromisoformat(str(valor)).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(valor or "")


def reporte_markdown(r: Dict[str, Any], docente: Optional[str] = None) -> str:
    """Informe descargable en Markdown con la estructura sobria del informe institucional (UTA - FISEI)."""
    from app.services.agente_herramientas import _nombre_curso  # evita importación circular
    m, d, a = r["metricas"], r["distribucion_estados"], r["alertas"]
    comp = m["componentes"]
    fmt = lambda v: "-" if v is None else f"{v:.2f}"  # noqa: E731
    asignatura = _nombre_curso(r["curso"]["fullname"]).replace(", paralelo", " - Paralelo")
    p = r["periodo"]
    lineas = [
        "# Informe académico del curso",
        "",
        "**Universidad Técnica de Ambato** · Facultad de Ingeniería en Sistemas, Electrónica e Industrial · "
        "Carrera de Software",
        "",
        "| Dato | Valor |", "|---|---|",
        f"| Asignatura | {asignatura} ({r['curso']['shortname']}) |",
        f"| Período académico | {p['nombre']} ({_fecha(p['inicio'])} - {_fecha(p['fin'])}) |",
        *([f"| Docente | {docente} |"] if docente else []),
        f"| Sincronización con Moodle UTA | {_fecha_hora(r['fecha_sincronizacion'])} |",
        f"| Fecha de emisión | {_fecha_hora(r['generado_en'])} |",
        "",
        "## 1. Métricas del curso",
        "",
        "| Indicador | Valor |", "|---|---|",
        f"| Estudiantes | {m['total_estudiantes']} |",
        f"| Promedio | {m['promedio']:.2f} / 10 |",
        f"| Mediana | {m['mediana']:.2f} |",
        f"| Nota mínima - máxima | {m['nota_minima']:.2f} - {m['nota_maxima']:.2f} |",
        f"| Desviación estándar | {m['desviacion_estandar']:.2f} |",
        f"| Aprobación | {m['porcentaje_aceptables']:.1f} % |",
        "",
        "| Nivel | Estudiantes |", "|---|---|",
        f"| Crítico | {m['criticos']} |",
        f"| En riesgo | {m['en_riesgo']} |",
        f"| Aceptable | {m['aceptables']} |",
        "",
        "| Componente | Promedio |", "|---|---|",
        f"| Exámenes (40 %) | {fmt(comp['acd'])} |",
        f"| Tareas (30 %) | {fmt(comp['tareas'])} |",
        f"| APE (30 %) | {fmt(comp['pae'])} |",
        *([""] + ["| Unidad | Promedio |", "|---|---|"]
          + [f"| Unidad {u[1:]} | {fmt(v)} |" for u, v in m["promedio_por_unidad"].items()]
          if m.get("promedio_por_unidad") else []),
        "",
        "## 2. Estado de las actividades",
        "",
        "| Estado | Registros | Estudiantes |", "|---|---|---|",
        f"| Calificado | {d['calificado']} | - |",
        f"| Nota 0 | {d['cero']} | {d['estudiantes_con_cero']} |",
        f"| Sin entrega | {d['sin_entrega']} | {d['estudiantes_sin_entrega']} |",
        f"| Pendiente de revisión | {d['pendiente']} | {d['estudiantes_con_pendiente']} |",
        "",
        "## 3. Alertas tempranas",
        "",
        "| Alerta | Cantidad |", "|---|---|",
        f"| Nota crítica | {a['r1_activas']} |",
        f"| Descenso sostenido | {a['r2_activas']} |",
        f"| Abiertas / en atención / publicadas | {a['abiertas']} / {a['atendidas']} / {a['publicadas']} |",
        f"| Cerradas / resueltas | {a['cerradas']} / {a['resueltas']} |",
    ]
    if r["estudiantes_prioritarios"]:
        lineas += ["", "| Estudiante prioritario | Nota final | Nivel | Alerta |", "|---|---|---|---|"]
        lineas += [f"| {e['nombres']} | {e['nota_final']:.2f} | {_NIVEL.get(e['nivel_riesgo'], e['nivel_riesgo'])} | "
                   f"{_ALERTA.get(e['regla_alerta'], e['regla_alerta'] or '-')} |" for e in r["estudiantes_prioritarios"]]
    lineas += ["", "## 4. Hallazgos"]
    for i, grupo in enumerate(r.get("hallazgos_grupos") or [{"titulo": "Hallazgos", "items": r["hallazgos"]}], 1):
        lineas += ["", f"### 4.{i}. {grupo['titulo']}", "", *[f"- {h}" for h in grupo["items"]]]
    lineas += ["", "## 5. Recomendaciones", "", *[f"{i}. {x}" for i, x in enumerate(r["recomendaciones"], 1)], ""]
    return "\n".join(lineas)
