from fastapi import APIRouter
from app.config import settings
from app.services.moodle_client import MoodleClient

router = APIRouter(prefix="/health", tags=["Health & Status"])


@router.get("")
async def check_health():
    """
    Estado general del Middleware y dependencias.
    """
    moodle_client = MoodleClient()
    moodle_status = await moodle_client.test_connection()

    return {
        "status": "online",
        "service": "Middleware FastAPI Moodle Analytics",
        "version": "1.0.0-sprint1",
        "institution": "FISEI - Universidad Técnica de Ambato",
        "environment": settings.ENVIRONMENT,
        "moodle_status": moodle_status,
        "ollama_host": settings.OLLAMA_HOST,
        "database_configured": bool(settings.DATABASE_URL)
    }
