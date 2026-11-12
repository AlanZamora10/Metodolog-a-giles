from fastapi import APIRouter, Depends

from app.routers.sincronizacion import get_current_docente, sincronizar_moodle

router = APIRouter(prefix="/sync", tags=["Sincronización"])


@router.post("/moodle")
async def trigger_moodle_sync(docente: dict = Depends(get_current_docente)):
    """Alias heredado de POST /api/sincronizacion (sincronización real con Moodle)."""
    return await sincronizar_moodle(docente)
