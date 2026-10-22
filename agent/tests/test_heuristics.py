import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.heuristics import HeuristicRulesEngine


def test_heuristic_diagnostic_critical_student():
    """
    Verifica que el motor heurístico HU-11B genere diagnósticos estructurados
    con menos de 250 caracteres e identifique la unidad crítica con mayor reprobación.
    """
    notas_actividades = {
        "MAT1-P1-U1-T1": 6.0,
        "MAT1-P1-U2-T2": 2.0,
        "MAT1-P1-U2-T3": 2.0,
        "MAT1-P1-U3-T4": 4.0,
        "MAT1-P1-U4-T5": 4.0
    }

    result = HeuristicRulesEngine.generate_diagnostic(
        id_number="U-05",
        nombres="Estudiante C",
        nota_final=3.50,
        notas_actividades=notas_actividades
    )

    assert "Unidad 2" in result["unidad_critica"]
    assert len(result["diagnostico"]) <= 250
    assert result["fuente"] == "motor_heuristico_hu11b"
    assert "Refuerzo" in result["tipo_accion_sugerida"]
