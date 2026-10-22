from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter
from app.schemas.academic import SystemLogResponse, AlertResponse

router = APIRouter(tags=["Logs y Alertas"])

# Almacén en memoria de logs del sistema (HU-16)
LOGS_STORE: List[Dict[str, Any]] = [
    {
        "id": 1,
        "timestamp": datetime.now().isoformat(),
        "tipo_proceso": "CARGA_DATOS",
        "estado": "EXITO",
        "mensaje": "Inicialización de esquema relacional analítico y seed data de HU-01.",
        "detalle": {"estudiantes": 7, "materias": 2, "parciales": 2, "unidades": 4}
    },
    {
        "id": 2,
        "timestamp": datetime.now().isoformat(),
        "tipo_proceso": "SINCRONIZACION",
        "estado": "EXITO",
        "mensaje": "Sincronización inicial de libro de calificaciones Moodle. 35 notas procesadas sin duplicados.",
        "detalle": {"curso": "MAT1", "calificaciones_extraidas": 35, "duplicados_evitados": 0}
    },
    {
        "id": 3,
        "timestamp": datetime.now().isoformat(),
        "tipo_proceso": "ANALISIS_IA",
        "estado": "EXITO",
        "mensaje": "Evaluación predictiva ejecutada. Detectadas 2 alertas Críticas (Estudiante C y D).",
        "detalle": {"total_evaluados": 7, "criticos": 2, "en_riesgo": 1, "modelo": "llama3.2:1b"}
    }
]

# Almacén de alertas tempranas (HU-08)
ALERTS_STORE: List[Dict[str, Any]] = [
    {
        "id": 1,
        "id_number": "U-05",
        "nombres": "Estudiante C",
        "nivel": "CRITICO",
        "unidad_critica": "Unidad 2: Lógica y Modelado",
        "motivo": "Nota ponderada 3.5/10 y tendencia descendente sostenida (-0.65). Falencias severas en Tema 2.3.",
        "diagnostico_ia": "El estudiante presenta dificultades severas de comprensión en la Unidad 2 (Tema 2.3). Se recomienda asignar una guía complementaria práctica y ejercicios razonados antes de la evaluación del segundo parcial.",
        "accion_sugerida": "Refuerzo Práctico: Guiado de Diagramación (Unidad 2)"
    },
    {
        "id": 2,
        "id_number": "U-06",
        "nombres": "Estudiante D",
        "nivel": "CRITICO",
        "unidad_critica": "Unidad 1: Fundamentos y Conceptos",
        "motivo": "Nota ponderada 4.5/10. Incumplimiento reiterado de talleres iniciales (Tema 1.1 = 3.5).",
        "diagnostico_ia": "El estudiante presenta vacíos conceptuales en fundamentos ágiles y modelado base. Requiere intervención tutorial y nivelación en rúbricas de evaluación.",
        "accion_sugerida": "Taller Nivelatorio de Fundamentos y Criterios Gherkin"
    },
    {
        "id": 3,
        "id_number": "U-08",
        "nombres": "Estudiante F",
        "nivel": "EN_RIESGO",
        "unidad_critica": "Unidad 2: Lógica y Modelado",
        "motivo": "Nota ponderada 6.2/10. Rendimiento en zona de riesgo académico (5.0 a 6.9).",
        "diagnostico_ia": "El estudiante mantiene notas aceptables en tareas pero desciende en evaluaciones de lógica. Reforzar antes del cierre del parcial.",
        "accion_sugerida": "Cuestionario de Autoevaluación y Refuerzo de Conceptos"
    }
]


def append_log(tipo_proceso: str, estado: str, mensaje: str, detalle: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    new_id = len(LOGS_STORE) + 1
    entry = {
        "id": new_id,
        "timestamp": datetime.now().isoformat(),
        "tipo_proceso": tipo_proceso,
        "estado": estado,
        "mensaje": mensaje,
        "detalle": detalle or {}
    }
    LOGS_STORE.append(entry)
    return entry


@router.get("/logs", response_model=List[SystemLogResponse])
async def list_logs():
    """
    Retorna los registros de sincronización y análisis del sistema (HU-16).
    """
    return LOGS_STORE


@router.get("/alerts", response_model=List[AlertResponse])
async def list_alerts():
    """
    Retorna la lista de alertas tempranas activas (HU-08).
    """
    return ALERTS_STORE
