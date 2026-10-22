import sys
from pathlib import Path

# Asegurar que el directorio del middleware esté en sys.path tanto para ejecución local como Docker
_middleware_dir = str(Path(__file__).resolve().parent.parent)
if _middleware_dir not in sys.path:
    sys.path.insert(0, _middleware_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, students, courses, sync, logs

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Middleware de Sincronización con Moodle y Capa Analítica de IA "
        "(FISEI - Universidad Técnica de Ambato)."
    ),
    version="1.0.0-sprint1",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configuración de CORS para el Frontend minimalista y consumo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de routers bajo el prefijo de API v1
api_prefix = "/api/v1"
app.include_router(health.router, prefix=api_prefix)
app.include_router(students.router, prefix=api_prefix)
app.include_router(courses.router, prefix=api_prefix)
app.include_router(sync.router, prefix=api_prefix)
app.include_router(logs.router, prefix=api_prefix)


@app.get("/", tags=["Root"])
async def root():
    return {
        "sistema": settings.PROJECT_NAME,
        "institucion": "FISEI - Universidad Técnica de Ambato",
        "sprint": "Sprint 1: Envisioning, diseño y entorno base",
        "docs": "/docs",
        "health": "/api/v1/health",
        "summary": "/api/v1/courses/MAT1/summary"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
