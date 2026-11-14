"""
Chat del agente con herramientas (Fase A) — consumido por el frontend React.

POST /api/v1/agent/chat   { "mensaje": "...", "course_id": 2 (opcional) }
  -> respuesta redactada sólo con datos reales, herramientas invocadas (nombre, parámetros, resultado),
     origen del plan (ollama_slm | reglas_deterministas). Cada herramienta queda en logs_sistema.
GET  /api/v1/agent/herramientas  -> catálogo de herramientas disponibles.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.routers.auth import get_current_docente
from app.services import agente_herramientas

router = APIRouter(prefix="/agent", tags=["Agente IA (chat con herramientas)"])


class ChatRequest(BaseModel):
    mensaje: str = Field(..., min_length=1, max_length=1000,
                         json_schema_extra={"example": "¿Qué estudiantes de POO necesitan atención?"})
    course_id: Optional[int] = Field(None, description="Curso de contexto (ID de Moodle), opcional")


@router.post("/chat")
async def chat(req: ChatRequest, docente: dict = Depends(get_current_docente)):
    return await agente_herramientas.conversar(req.mensaje, docente, req.course_id)


@router.get("/herramientas")
async def herramientas(docente: dict = Depends(get_current_docente)):
    return [{"nombre": n, **d} for n, d in agente_herramientas.CATALOGO.items()]
