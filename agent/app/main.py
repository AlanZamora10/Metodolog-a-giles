from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001)
