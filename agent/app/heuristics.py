"""
==============================================================================
SERVICIO: MOTOR DE REGLAS HEURÍSTICAS DE RESPALDO (HU-11B)
Responsable: Johan Borja (Agente IA & Datos)
==============================================================================
Este archivo implementa el motor de reglas deterministas que se activa
automáticamente si el modelo de lenguaje de Ollama demora más de 10 segundos
o no está disponible, garantizando que el docente siempre reciba un diagnóstico.
==============================================================================
"""

from typing import Dict, Any, List


class HeuristicRulesEngine:
    """
    Motor de reglas para generar diagnósticos pedagógicos de respaldo.
    """

    @classmethod
    def generate_diagnostic(
        cls,
        id_number: str,
        nombres: str,
        nota_final: float,
        notas_actividades: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Analiza las notas de las tareas de un estudiante y genera un diagnóstico
        didáctico de máximo 250 caracteres indicando la unidad más crítica.
        """
        # Paso 1: Agrupar las notas por cada unidad (ej: U1, U2, U3, U4)
        notas_por_unidad: Dict[str, List[float]] = {}
        for codigo_actividad, nota in notas_actividades.items():
            partes = codigo_actividad.split("-")
            # El código de la unidad está en la tercera posición: MAT1-P1-U2-T3 -> U2
            codigo_u = partes[2] if len(partes) > 2 else "U1"
            notas_por_unidad.setdefault(codigo_u, []).append(nota)

        # Paso 2: Identificar la unidad que tenga el promedio de notas más bajo
        unidad_critica_cod = "U2"
        menor_promedio = 10.0

        for cod_u, lista_notas in notas_por_unidad.items():
            promedio_u = sum(lista_notas) / len(lista_notas)
            if promedio_u < menor_promedio:
                menor_promedio = promedio_u
                unidad_critica_cod = cod_u

        # Paso 3: Asignar el nombre descriptivo de la unidad
        nombres_unidades = {
            "U1": "Unidad 1: Fundamentos y Conceptos",
            "U2": "Unidad 2: Lógica y Modelado",
            "U3": "Unidad 3: Estructuras Aplicadas",
            "U4": "Unidad 4: Arquitectura e Integración"
        }
        unidad_critica = nombres_unidades.get(unidad_critica_cod, f"Unidad {unidad_critica_cod}")

        # Paso 4: Redactar el diagnóstico según el semáforo (máximo 250 caracteres por HU-11A)
        if nota_final < 5.0:
            diagnostico = (
                f"El estudiante presenta dificultades severas de comprensión en la {unidad_critica}. "
                f"Se recomienda asignar una guía complementaria práctica y ejercicios razonados."
            )[:250]
            tipo_accion = f"Refuerzo Práctico Guiado ({unidad_critica_cod})"
        elif nota_final < 7.0:
            diagnostico = (
                f"El estudiante mantiene rendimiento en riesgo ({nota_final}/10). Requiere afianzar "
                f"conceptos clave en {unidad_critica} antes del cierre de parcial."
            )[:250]
            tipo_accion = f"Cuestionario de Autoevaluación ({unidad_critica_cod})"
        else:
            diagnostico = (
                f"El estudiante mantiene un rendimiento aceptable ({nota_final}/10). Se recomienda "
                f"mantener el ritmo y realizar lecturas avanzadas de profundización."
            )[:250]
            tipo_accion = "Actividad Opcional de Profundización"

        return {
            "unidad_critica": unidad_critica,
            "diagnostico": diagnostico,
            "tipo_accion_sugerida": tipo_accion,
            "fuente": "motor_heuristico_hu11b"
        }
