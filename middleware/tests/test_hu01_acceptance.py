import sys
import os

# Asegurar path para importar script de seed y servicios
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.seed_moodle_course import validar_criterios_hu01, COURSE_DATA


def test_hu01_acceptance_criteria_complete():
    """
    Criterio de Aceptación Formal HU-01:
    Dado que existe el entorno base y script de carga del curso simulado
    Cuando se valida el curso de prueba
    Entonces:
      - Contiene exactamente 2 materias.
      - Contiene 7 estudiantes (U-03 a U-09, Estudiante A a G).
      - Contiene 2 parciales y 4 unidades temáticas ("Unidad 1" a "Unidad 4").
      - Cada actividad tiene un ID number normalizado [MATERIA]-[PARCIAL]-[UNIDAD]-[TEMA].
      - Al menos 2 estudiantes tienen nota ponderada menor a 5.0 (casos críticos).
    """
    resultado = validar_criterios_hu01()

    # 1. Verificación global de aprobación
    assert resultado["aprobado"] is True, f"Fallo en HU-01: {resultado}"

    # 2. Verificación de 2 materias
    assert resultado["materias"] == 2
    codigos_materias = [m["codigo"] for m in COURSE_DATA["materias"]]
    assert "MAT1" in codigos_materias
    assert "MAT2" in codigos_materias

    # 3. Verificación de 7 estudiantes (U-03 a U-09)
    assert resultado["estudiantes"] == 7
    ids_estudiantes = [e["id_number"] for e in COURSE_DATA["estudiantes"]]
    assert ids_estudiantes == ["U-03", "U-04", "U-05", "U-06", "U-07", "U-08", "U-09"]

    # 4. Verificación de 4 unidades temáticas
    assert resultado["unidades"] == 4

    # 5. Verificación de 2 parciales
    assert resultado["parciales"] == 2

    # 6. Verificación de actividades con ID normalizado
    assert len(resultado["errores_id"]) == 0

    # 7. Verificación de al menos 2 estudiantes críticos (< 5.0)
    assert resultado["casos_criticos"] >= 2

    # 8. Verificación de casos específicos (Estudiante C = 3.50, Estudiante D = 4.50)
    eval_c = next(e for e in resultado["evaluaciones"] if e["id_number"] == "U-05")
    assert eval_c["nota_final"] == 3.50
    assert eval_c["nivel"] == "CRITICO"

    eval_d = next(e for e in resultado["evaluaciones"] if e["id_number"] == "U-06")
    assert eval_d["nota_final"] == 4.50
    assert eval_d["nivel"] == "CRITICO"
