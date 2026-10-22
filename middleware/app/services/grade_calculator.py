from typing import Dict, Any, List, Optional
import numpy as np


class GradeCalculator:
    """
    Calculadora del modelo oficial de calificaciones UTA (FISEI).
    Ponderación:
      - Trabajo Autónomo : 40% (0.40)
      - Tareas / Talleres: 30% (0.30)
      - PAE (Prácticas)  : 30% (0.30)
    Fórmula: Nota Final = 0.40 * Autónomo + 0.30 * Tareas + 0.30 * PAE
    """

    WEIGHT_AUTONOMO = 0.40
    WEIGHT_TAREAS = 0.30
    WEIGHT_PAE = 0.30

    THRESHOLD_CRITICAL = 5.00
    THRESHOLD_RISK = 7.00

    @classmethod
    def calculate_weighted_grade(
        cls,
        autonomo: float,
        tareas: float,
        pae: float
    ) -> float:
        """
        Calcula la nota ponderada redondeada a 2 decimales.
        """
        if any(g < 0.0 or g > 10.0 for g in [autonomo, tareas, pae]):
            raise ValueError("Las calificaciones deben estar en el rango de 0.00 a 10.00.")

        weighted = (
            (cls.WEIGHT_AUTONOMO * autonomo)
            + (cls.WEIGHT_TAREAS * tareas)
            + (cls.WEIGHT_PAE * pae)
        )
        return round(weighted, 2)

    @classmethod
    def classify_risk(cls, final_grade: float, slope: Optional[float] = None) -> str:
        """
        Clasifica el nivel de riesgo del estudiante:
        - CRITICO: Nota < 5.0 o tendencia descendente sostenida (slope < -0.25 con nota < 7.0)
        - EN_RIESGO: 5.0 <= Nota < 7.0
        - ACEPTABLE: Nota >= 7.0
        """
        if final_grade < cls.THRESHOLD_CRITICAL:
            return "CRITICO"

        if slope is not None and slope < -0.25 and final_grade < cls.THRESHOLD_RISK:
            return "CRITICO"

        if final_grade < cls.THRESHOLD_RISK:
            return "EN_RIESGO"

        return "ACEPTABLE"

    @classmethod
    def calculate_trend(cls, grades_sequence: List[float]) -> Dict[str, Any]:
        """
        Calcula la regresión lineal simple sobre la secuencia de tareas/actividades (HU-10A).
        Retorna la pendiente, la etiqueta de tendencia ('SUBE', 'BAJA', 'ESTABLE')
        y la probabilidad estimada de aprobación.
        """
        if not grades_sequence or len(grades_sequence) < 2:
            return {
                "slope": 0.0,
                "trend": "ESTABLE",
                "probability_approval": 50
            }

        x = np.arange(len(grades_sequence))
        y = np.array(grades_sequence)

        # Regresión por mínimos cuadrados
        A = np.vstack([x, np.ones(len(x))]).T
        slope, intercept = np.linalg.lstsq(A, y, rcond=None)[0]
        slope = round(float(slope), 3)

        if slope > 0.25:
            trend = "SUBE"
        elif slope < -0.25:
            trend = "BAJA"
        else:
            trend = "ESTABLE"

        # Estimación heurística de probabilidad de aprobación (0% a 100%)
        latest_avg = float(np.mean(y[-2:])) if len(y) >= 2 else float(y[0])
        prob = int(np.clip((latest_avg / 10.0) * 100 + (slope * 20), 5, 99))

        return {
            "slope": slope,
            "trend": trend,
            "probability_approval": prob
        }
