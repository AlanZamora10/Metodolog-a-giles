import os
import json
import logging
import httpx
from typing import Dict, Any
from app.heuristics import HeuristicRulesEngine

logger = logging.getLogger("agent_service")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
INFERENCE_TIMEOUT = float(os.getenv("AGENT_INFERENCE_TIMEOUT_SECONDS", "10.0"))


class OllamaAgent:
    """
    Cliente para inferencia local de SLM mediante Ollama.
    Garantiza el criterio de tiempo de respuesta (< 8-10s) con fallback automático (HU-11B).
    """

    @classmethod
    async def analyze_student(
        cls,
        id_number: str,
        nombres: str,
        nota_final: float,
        notas_actividades: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Envía prompt estructurado a Ollama. Si la respuesta excede 10s o falla,
        activa el motor de plantillas heurísticas (HU-11B).
        """
        prompt = (
            f"Eres un Asistente Pedagógico IA para la FISEI - UTA. Analiza el siguiente estudiante:\n"
            f"- Nombre: {nombres} (ID: {id_number})\n"
            f"- Nota Ponderada Actual: {nota_final}/10\n"
            f"- Calificaciones por Actividad: {json.dumps(notas_actividades)}\n\n"
            f"Responde estrictamente en formato JSON válido con las claves:\n"
            f'{{"unidad_critica": "<nombre de la unidad>", "diagnostico": "<máximo 250 caracteres>", "tipo_accion_sugerida": "<acción recomendada>"}}'
        )

        try:
            async with httpx.AsyncClient(timeout=INFERENCE_TIMEOUT) as client:
                res = await client.post(
                    f"{OLLAMA_HOST}/api/generate",
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    response_text = data.get("response", "{}")
                    parsed = json.loads(response_text)
                    if "unidad_critica" in parsed and "diagnostico" in parsed:
                        # Asegurar restricción de máx 250 caracteres
                        parsed["diagnostico"] = str(parsed["diagnostico"])[:250]
                        parsed["fuente"] = "ollama_slm"
                        return parsed
        except (httpx.TimeoutException, httpx.RequestError, json.JSONDecodeError, Exception) as ex:
            logger.warning(
                f"Inferencia con Ollama no disponible ({ex}). Activando motor de respaldo heurístico (HU-11B)."
            )

        # Fallback Heurístico transparente
        return HeuristicRulesEngine.generate_diagnostic(
            id_number=id_number,
            nombres=nombres,
            nota_final=nota_final,
            notas_actividades=notas_actividades
        )
