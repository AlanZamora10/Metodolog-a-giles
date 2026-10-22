"""
==============================================================================
SERVICIO: CALCULADORA DE CALIFICACIONES (FISEI - UTA)
Responsable: Johan Borja (Arquitectura & DB) y Justin Ojeda (Backend)
==============================================================================
Este archivo contiene las funciones para calcular la nota final ponderada oficial
de la Universidad Técnica de Ambato (UTA) y analizar el riesgo del estudiante.

Fórmula oficial:
  Nota Final = (0.40 * Autónomo) + (0.30 * Tareas) + (0.30 * PAE)
==============================================================================
"""

from typing import Dict, Any, List, Optional


class GradeCalculator:
    """
    Clase utilitaria para cálculo y clasificación de notas de los estudiantes.
    """

    # Porcentajes oficiales de la ponderación
    PESO_AUTONOMO = 0.40  # 40%
    PESO_TAREAS = 0.30    # 30%
    PESO_PAE = 0.30       # 30%

    # Umbrales del semáforo pedagógico
    UMBRAL_CRITICO = 5.00  # Menor a 5.0 es Crítico
    UMBRAL_ACEPTABLE = 7.00  # 7.0 o más es Aceptable

    @classmethod
    def calculate_weighted_grade(
        cls,
        autonomo: float,
        tareas: float,
        pae: float
    ) -> float:
        """
        Calcula la nota ponderada oficial sobre 10.00 puntos.
        
        Parámetros:
          - autonomo: Calificación del componente autónomo (0 a 10)
          - tareas: Calificación de tareas y talleres (0 a 10)
          - pae: Calificación de prácticas de aplicación y experimentación (0 a 10)
        
        Retorna:
          - Nota final redondeada a dos decimales.
        """
        # Validación básica de rango permitido
        if autonomo < 0.0 or autonomo > 10.0:
            raise ValueError("La nota de Autónomo debe estar entre 0.00 y 10.00")
        if tareas < 0.0 or tareas > 10.0:
            raise ValueError("La nota de Tareas debe estar entre 0.00 y 10.00")
        if pae < 0.0 or pae > 10.0:
            raise ValueError("La nota de PAE debe estar entre 0.00 y 10.00")

        # Paso 1: Multiplicar cada nota por su peso respectivo
        parcial_autonomo = cls.PESO_AUTONOMO * autonomo
        parcial_tareas = cls.PESO_TAREAS * tareas
        parcial_pae = cls.PESO_PAE * pae

        # Paso 2: Sumar los tres componentes y redondear a 2 decimales
        nota_final = parcial_autonomo + parcial_tareas + parcial_pae
        return round(nota_final, 2)

    @classmethod
    def classify_risk(cls, final_grade: float, slope: Optional[float] = None) -> str:
        """
        Determina el semáforo de riesgo académico del estudiante:
          - 'CRITICO': Si tiene nota menor a 5.0 o si tiene tendencia descendente.
          - 'EN_RIESGO': Si su nota está entre 5.0 y 6.99.
          - 'ACEPTABLE': Si su nota es 7.0 o superior.
        """
        # Caso 1: Nota menor a 5.0 es reprobación crítica directa
        if final_grade < cls.UMBRAL_CRITICO:
            return "CRITICO"

        # Caso 2: Si tiene tendencia a la baja sostenida (pendiente menor a -0.25)
        if slope is not None and slope < -0.25 and final_grade < cls.UMBRAL_ACEPTABLE:
            return "CRITICO"

        # Caso 3: Nota entre 5.0 y 6.99
        if final_grade < cls.UMBRAL_ACEPTABLE:
            return "EN_RIESGO"

        # Caso 4: 7.0 o más es aprobado/aceptable
        return "ACEPTABLE"

    @classmethod
    def calculate_trend(cls, grades_sequence: List[float]) -> Dict[str, Any]:
        """
        Calcula la tendencia académica del estudiante utilizando la fórmula básica
        de regresión lineal simple:
        
            pendiente (m) = (n * sum(x*y) - sum(x) * sum(y)) / (n * sum(x^2) - (sum(x))^2)
            
        Donde:
          - x: posición de la actividad (0, 1, 2, 3...)
          - y: nota de la actividad
        """
        # Si no hay suficientes notas, dejamos tendencia estable
        if not grades_sequence or len(grades_sequence) < 2:
            return {
                "slope": 0.0,
                "trend": "ESTABLE",
                "probability_approval": 50
            }

        n = len(grades_sequence)

        # Paso 1: Calcular sumatorias básicas
        sum_x = 0
        sum_y = 0
        sum_xy = 0
        sum_x2 = 0

        for i in range(n):
            x = i
            y = grades_sequence[i]
            sum_x += x
            sum_y += y
            sum_xy += (x * y)
            sum_x2 += (x * x)

        # Paso 2: Aplicar la fórmula de la pendiente
        denominador = (n * sum_x2) - (sum_x * sum_x)
        if denominador == 0:
            slope = 0.0
        else:
            numerador = (n * sum_xy) - (sum_x * sum_y)
            slope = round(numerador / denominador, 3)

        # Paso 3: Clasificar si la tendencia sube, baja o es estable
        if slope > 0.25:
            trend = "SUBE"
        elif slope < -0.25:
            trend = "BAJA"
        else:
            trend = "ESTABLE"

        # Paso 4: Estimar porcentaje aproximado de aprobación
        ultimas_notas = grades_sequence[-2:]
        promedio_reciente = sum(ultimas_notas) / len(ultimas_notas)
        
        # Cálculo de probabilidad base (entre 5% y 99%)
        prob_estimada = int((promedio_reciente / 10.0) * 100 + (slope * 20))
        prob_ajustada = max(5, min(99, prob_estimada))

        return {
            "slope": slope,
            "trend": trend,
            "probability_approval": prob_ajustada
        }
