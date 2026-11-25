"""
Chat del agente con herramientas (Fase A) — consumido por el frontend React.

POST /api/v1/agent/chat   { "mensaje": "...", "course_id": 2 (opcional) }
  -> respuesta redactada sólo con datos reales, herramientas invocadas (nombre, parámetros, resultado),
     origen del plan (ollama_slm | reglas_deterministas). Cada herramienta queda en logs_sistema.
GET  /api/v1/agent/herramientas  -> catálogo de herramientas disponibles.
GET  /api/v1/agent/guia-pdf?id_number=U-15&course_id=3 -> guía oficial de refuerzo (PDF) del estudiante.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.routers.auth import get_current_docente
from app.services import agente_herramientas
from app.services.guia_pdf import generar_guia_pdf

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


@router.get("/guia-pdf")
async def guia_pdf(id_number: str = Query(..., min_length=1, max_length=30), course_id: Optional[int] = Query(None),
                   docente: dict = Depends(get_current_docente)):
    """Guía oficial de refuerzo UTA - FISEI (PDF) de un estudiante del docente; se abre en el navegador."""
    try:
        datos, curso, e = agente_herramientas.guia_de_estudiante(docente, id_number, course_id)
    except agente_herramientas.HerramientaError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    if e["id_number"].upper() != id_number.strip().upper():
        raise HTTPException(status_code=404, detail=f"No se encontró al estudiante {id_number} en sus cursos.")
    guia = generar_guia_pdf(**datos)
    return Response(guia["pdf"], media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{guia["nombre"]}"'})
