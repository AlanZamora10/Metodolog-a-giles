from fastapi import APIRouter
from app.schemas.academic import CourseSummary
from app.routers.students import STUDENTS_STORE, _build_student_response

router = APIRouter(prefix="/courses", tags=["Cursos"])


@router.get("/MAT1/summary", response_model=CourseSummary)
async def get_mat1_summary():
    """
    Resumen general de métricas del curso MAT1 (Panel Mockup 1).
    """
    return await get_course_summary("MAT1")


@router.get("/{course_code}/summary", response_model=CourseSummary)
async def get_course_summary(course_code: str):
    """
    Resumen general dinámico de métricas por código de curso (Panel Mockup 1).
    """
    students_resp = [_build_student_response(st) for st in STUDENTS_STORE]

    total = len(students_resp)
    criticos = sum(1 for s in students_resp if s.nivel_riesgo == "CRITICO")
    en_riesgo = sum(1 for s in students_resp if s.nivel_riesgo == "EN_RIESGO")
    aceptables = sum(1 for s in students_resp if s.nivel_riesgo == "ACEPTABLE")
    promedio = round(sum(s.nota_final for s in students_resp) / total, 2) if total else 0.0

    nombre_materia = "Metodologías Ágiles" if course_code.upper() == "MAT1" else "Ingeniería de Software"

    return CourseSummary(
        materia_codigo=course_code.upper(),
        materia_nombre=nombre_materia,
        promedio_general=promedio,
        total_estudiantes=total,
        estudiantes_criticos=criticos,
        estudiantes_en_riesgo=en_riesgo,
        estudiantes_aceptables=aceptables,
        alertas_detectadas=criticos,
        estudiantes=students_resp
    )


@router.get("")
async def list_courses():
    """
    Lista las 2 materias del curso simulado de prueba (HU-01).
    """
    return [
        {
            "codigo": "MAT1",
            "nombre": "Metodologías Ágiles",
            "carrera": "Ingeniería de Software - FISEI",
            "docente": "Ing. Roberto Gómez",
            "parciales": [1, 2],
            "unidades": ["Unidad 1", "Unidad 2", "Unidad 3", "Unidad 4"]
        },
        {
            "codigo": "MAT2",
            "nombre": "Ingeniería de Software",
            "carrera": "Ingeniería de Software - FISEI",
            "docente": "Ing. Roberto Gómez",
            "parciales": [1, 2],
            "unidades": ["Unidad 1", "Unidad 2", "Unidad 3", "Unidad 4"]
        }
    ]
