from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class StudentBase(BaseModel):
    id_number: str = Field(..., json_schema_extra={"example": "U-03"})
    nombres: str = Field(..., json_schema_extra={"example": "Estudiante A"})
    email: str = Field(..., json_schema_extra={"example": "estudiante.a@uta.edu.ec"})


class WeightedGradeResponse(BaseModel):
    id_number: str
    nombres: str
    email: str
    autonomo: float = Field(..., ge=0.0, le=10.0)
    tareas: float = Field(..., ge=0.0, le=10.0)
    pae: float = Field(..., ge=0.0, le=10.0)
    nota_final: float = Field(..., ge=0.0, le=10.0)
    nivel_riesgo: str = Field(..., json_schema_extra={"example": "CRITICO"})
    tendencia: str = Field(..., json_schema_extra={"example": "BAJA"})
    pendiente: float
    probabilidad_aprobacion: int
    notas_actividades: Dict[str, float] = {}


class CourseSummary(BaseModel):
    materia_codigo: str
    materia_nombre: str
    promedio_general: float
    total_estudiantes: int
    estudiantes_criticos: int
    estudiantes_en_riesgo: int
    estudiantes_aceptables: int
    alertas_detectadas: int
    estudiantes: List[WeightedGradeResponse]


class SystemLogResponse(BaseModel):
    id: int
    timestamp: str
    tipo_proceso: str
    estado: str
    mensaje: str
    detalle: Optional[Dict[str, Any]] = None


class AlertResponse(BaseModel):
    id: int
    id_number: str
    nombres: str
    nivel: str
    unidad_critica: str
    motivo: str
    diagnostico_ia: str
    accion_sugerida: str
