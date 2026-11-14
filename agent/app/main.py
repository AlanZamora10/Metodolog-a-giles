import sys
from pathlib import Path

# Asegurar que el directorio del agente esté en sys.path
_agent_dir = str(Path(__file__).resolve().parent.parent)
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from app import chat_planner
from app.ollama_client import OllamaAgent

app = FastAPI(
    title="Servicio de Análisis Académico y Agente IA",
    description="Microservicio de análisis pedagógico con soporte de Ollama SLM y motor de reglas heurísticas.",
    version="1.0.0-sprint1"
)


class AnalysisRequest(BaseModel):
    id_number: str
    nombres: str
    nota_final: float
    notas_actividades: Dict[str, float]


@app.get("/health")
async def health():
    return {
        "status": "online",
        "service": "Agente IA Académico",
        "fallback_heuristico_habilitado": True
    }


@app.post("/api/v1/analyze")
async def analyze(req: AnalysisRequest):
    result = await OllamaAgent.analyze_student(
        id_number=req.id_number,
        nombres=req.nombres,
        nota_final=req.nota_final,
        notas_actividades=req.notas_actividades
    )
    return result


class PlanRequest(BaseModel):
    mensaje: str
    herramientas: List[Dict[str, Any]]
    cursos: List[Dict[str, Any]] = []
    course_id: Optional[int] = None


@app.post("/api/v1/chat/plan")
async def plan(req: PlanRequest):
    """Propone qué herramientas del middleware invocar (Ollama tool calling); plan vacío si no hay LLM."""
    return await chat_planner.planificar(req.mensaje, req.herramientas, req.cursos, req.course_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001)
