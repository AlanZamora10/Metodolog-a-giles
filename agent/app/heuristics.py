from typing import Dict, Any, List


class HeuristicRulesEngine:
    """
    Motor de Plantillas Heurísticas de Respaldo (HU-11B).
    Se activa automáticamente si el modelo de lenguaje en Ollama excede el timeout de 10s
    o produce una salida inválida, garantizando alta disponibilidad del sistema.
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
        Analiza las calificaciones y genera un diagnóstico estructurado según reglas pedagógicas.
        """
        # Identificar la unidad con la calificación más baja
        unidades_promedios: Dict[str, List[float]] = {}
        for act_id, nota in notas_actividades.items():
            # Extraer unidad ej: U1, U2
            partes = act_id.split("-")
            unidad_key = partes[2] if len(partes) > 2 else "U1"
            unidades_promedios.setdefault(unidad_key, []).append(nota)

        unidad_critica_cod = "U2"
        menor_promedio = 10.0

        for u, notas in unidades_promedios.items():
            avg = sum(notas) / len(notas)
            if avg < menor_promedio:
                menor_promedio = avg
                unidad_critica_cod = u

        # Mapeo de nombres descriptivos
        unidad_nombres = {
            "U1": "Unidad 1: Fundamentos y Conceptos",
            "U2": "Unidad 2: Lógica y Modelado",
            "U3": "Unidad 3: Estructuras Aplicadas",
            "U4": "Unidad 4: Arquitectura e Integración"
        }
        unidad_critica = unidad_nombres.get(unidad_critica_cod, f"Unidad {unidad_critica_cod}")

        # Generar diagnóstico conciso (máximo 250 caracteres según HU-11A)
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
