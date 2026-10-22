import pytest
from app.services.grade_calculator import GradeCalculator


def test_weighted_grade_exact_calculation():
    """
    Verifica que la fórmula oficial UTA:
    Nota Final = (0.40 * Autónomo) + (0.30 * Tareas) + (0.30 * PAE)
    calcule con diferencia 0.00 respecto al cálculo manual redondeado a 2 decimales (HU-05).
    """
    # Caso 1: Notas máximas
    assert GradeCalculator.calculate_weighted_grade(10.0, 10.0, 10.0) == 10.00

    # Caso 2: Estudiante C (Caso Crítico < 5.0)
    # Autónomo: 3.50, Tareas: 3.00, PAE: 4.00 -> (3.5*0.4) + (3*0.3) + (4*0.3) = 1.4 + 0.9 + 1.2 = 3.50
    assert GradeCalculator.calculate_weighted_grade(3.50, 3.00, 4.00) == 3.50

    # Caso 3: Estudiante D (Caso Crítico < 5.0)
    # Autónomo: 4.50, Tareas: 4.00, PAE: 5.00 -> (4.5*0.4) + (4*0.3) + (5*0.3) = 1.8 + 1.2 + 1.5 = 4.50
    assert GradeCalculator.calculate_weighted_grade(4.50, 4.00, 5.00) == 4.50

    # Caso 4: Estudiante F (En Riesgo)
    # Autónomo: 6.50, Tareas: 6.00, PAE: 6.00 -> (6.5*0.4) + (6*0.3) + (6*0.3) = 2.6 + 1.8 + 1.8 = 6.20
    assert GradeCalculator.calculate_weighted_grade(6.50, 6.00, 6.00) == 6.20

    # Caso 5: Estudiante A (Aceptable)
    assert GradeCalculator.calculate_weighted_grade(8.00, 8.00, 8.00) == 8.00


def test_invalid_grade_range_raises_error():
    """
    Verifica que no se acepten notas fuera del rango [0.00, 10.00].
    """
    with pytest.raises(ValueError):
        GradeCalculator.calculate_weighted_grade(-1.0, 8.0, 8.0)

    with pytest.raises(ValueError):
        GradeCalculator.calculate_weighted_grade(8.0, 10.5, 8.0)


def test_classify_risk_levels():
    """
    Verifica la clasificación por semáforo institucional:
    - Crítico: < 5.0
    - En Riesgo: 5.0 a 6.99
    - Aceptable: >= 7.0
    """
    assert GradeCalculator.classify_risk(4.99) == "CRITICO"
    assert GradeCalculator.classify_risk(3.50) == "CRITICO"
    assert GradeCalculator.classify_risk(5.00) == "EN_RIESGO"
    assert GradeCalculator.classify_risk(6.90) == "EN_RIESGO"
    assert GradeCalculator.classify_risk(7.00) == "ACEPTABLE"
    assert GradeCalculator.classify_risk(8.50) == "ACEPTABLE"


def test_trend_and_slope_calculation():
    """
    Verifica el cálculo de regresión lineal simple (HU-10A).
    """
    # Secuencia descendente (ej: 6.0, 4.0, 3.0, 2.0)
    res_baja = GradeCalculator.calculate_trend([6.0, 4.0, 3.0, 2.0])
    assert res_baja["slope"] < -0.25
    assert res_baja["trend"] == "BAJA"

    # Secuencia ascendente (ej: 5.0, 6.0, 7.5, 8.5)
    res_sube = GradeCalculator.calculate_trend([5.0, 6.0, 7.5, 8.5])
    assert res_sube["slope"] > 0.25
    assert res_sube["trend"] == "SUBE"
