from fastapi import APIRouter, HTTPException
from typing import List
from app.schemas.academic import WeightedGradeResponse
from app.services.grade_calculator import GradeCalculator

router = APIRouter(prefix="/students", tags=["Estudiantes"])

# Dataset en memoria alimentado desde la base o simulación HU-01
STUDENTS_STORE = [
    {
        "id_number": "U-03",
        "nombres": "Estudiante A",
        "email": "estudiante.a@uta.edu.ec",
        "autonomo": 8.00,
        "tareas": 8.00,
        "pae": 8.00,
        "pendiente": 0.350,
        "probabilidad_aprobacion": 92,
        "notas_actividades": {
            "MAT1-P1-U1-T1": 8.0,
            "MAT1-P1-U2-T2": 8.0,
            "MAT1-P1-U2-T3": 8.0,
            "MAT1-P1-U3-T4": 8.0,
            "MAT1-P1-U4-T5": 8.0
        }
    },
    {
        "id_number": "U-04",
        "nombres": "Estudiante B",
        "email": "estudiante.b@uta.edu.ec",
        "autonomo": 8.50,
        "tareas": 8.50,
        "pae": 8.50,
        "pendiente": 0.050,
        "probabilidad_aprobacion": 95,
        "notas_actividades": {
            "MAT1-P1-U1-T1": 8.5,
            "MAT1-P1-U2-T2": 8.5,
            "MAT1-P1-U2-T3": 8.5,
            "MAT1-P1-U3-T4": 8.5,
            "MAT1-P1-U4-T5": 8.5
        }
    },
    {
        "id_number": "U-05",
        "nombres": "Estudiante C",
        "email": "estudiante.c@uta.edu.ec",
        "autonomo": 3.50,
        "tareas": 3.00,
        "pae": 4.00,
        "pendiente": -0.650,
        "probabilidad_aprobacion": 22,
        "notas_actividades": {
            "MAT1-P1-U1-T1": 6.0,
            "MAT1-P1-U2-T2": 2.0,
            "MAT1-P1-U2-T3": 2.0,
            "MAT1-P1-U3-T4": 4.0,
            "MAT1-P1-U4-T5": 4.0
        }
    },
    {
        "id_number": "U-06",
        "nombres": "Estudiante D",
        "email": "estudiante.d@uta.edu.ec",
        "autonomo": 4.50,
        "tareas": 4.00,
        "pae": 5.00,
        "pendiente": -0.380,
        "probabilidad_aprobacion": 38,
        "notas_actividades": {
            "MAT1-P1-U1-T1": 3.5,
            "MAT1-P1-U2-T2": 5.5,
            "MAT1-P1-U2-T3": 4.0,
            "MAT1-P1-U3-T4": 4.0,
            "MAT1-P1-U4-T5": 5.0
        }
    },
    {
        "id_number": "U-07",
        "nombres": "Estudiante E",
        "email": "estudiante.e@uta.edu.ec",
        "autonomo": 8.00,
        "tareas": 7.00,
        "pae": 7.67,
        "pendiente": 0.280,
        "probabilidad_aprobacion": 88,
        "notas_actividades": {
            "MAT1-P1-U1-T1": 8.0,
            "MAT1-P1-U2-T2": 8.0,
            "MAT1-P1-U2-T3": 7.0,
            "MAT1-P1-U3-T4": 7.0,
            "MAT1-P1-U4-T5": 7.6
        }
    },
    {
        "id_number": "U-08",
        "nombres": "Estudiante F",
        "email": "estudiante.f@uta.edu.ec",
        "autonomo": 6.50,
        "tareas": 6.00,
        "pae": 6.00,
        "pendiente": -0.100,
        "probabilidad_aprobacion": 62,
        "notas_actividades": {
            "MAT1-P1-U1-T1": 7.0,
            "MAT1-P1-U2-T2": 6.0,
            "MAT1-P1-U2-T3": 6.0,
            "MAT1-P1-U3-T4": 6.0,
            "MAT1-P1-U4-T5": 6.0
        }
    },
    {
        "id_number": "U-09",
        "nombres": "Estudiante G",
        "email": "estudiante.g@uta.edu.ec",
        "autonomo": 8.50,
        "tareas": 8.00,
        "pae": 8.70,
        "pendiente": 0.420,
        "probabilidad_aprobacion": 94,
        "notas_actividades": {
            "MAT1-P1-U1-T1": 8.5,
            "MAT1-P1-U2-T2": 8.5,
            "MAT1-P1-U2-T3": 8.0,
            "MAT1-P1-U3-T4": 8.0,
            "MAT1-P1-U4-T5": 8.7
        }
    }
]


def _build_student_response(item: dict) -> WeightedGradeResponse:
    nota_final = GradeCalculator.calculate_weighted_grade(
        autonomo=item["autonomo"],
        tareas=item["tareas"],
        pae=item["pae"]
    )
    nivel = GradeCalculator.classify_risk(nota_final, item.get("pendiente"))
    
    # Determinar etiqueta de tendencia según la pendiente
    pendiente = item.get("pendiente", 0.0)
    if pendiente > 0.25:
        tendencia = "SUBE"
    elif pendiente < -0.25:
        tendencia = "BAJA"
    else:
        tendencia = "ESTABLE"

    return WeightedGradeResponse(
        id_number=item["id_number"],
        nombres=item["nombres"],
        email=item["email"],
        autonomo=item["autonomo"],
        tareas=item["tareas"],
        pae=item["pae"],
        nota_final=nota_final,
        nivel_riesgo=nivel,
        tendencia=tendencia,
        pendiente=pendiente,
        probabilidad_aprobacion=item.get("probabilidad_aprobacion", 50),
        notas_actividades=item.get("notas_actividades", {})
    )


@router.get("", response_model=List[WeightedGradeResponse])
async def list_students():
    """
    Lista todos los estudiantes con su nota ponderada y nivel de riesgo.
    """
    return [_build_student_response(st) for st in STUDENTS_STORE]


@router.get("/{id_number}", response_model=WeightedGradeResponse)
async def get_student_detail(id_number: str):
    """
    Obtiene el detalle individual de un estudiante con desglose de actividades.
    """
    for st in STUDENTS_STORE:
        if st["id_number"].upper() == id_number.upper():
            return _build_student_response(st)
    raise HTTPException(status_code=404, detail=f"Estudiante con ID '{id_number}' no encontrado.")
