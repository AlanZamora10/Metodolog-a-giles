import time
from fastapi import APIRouter
from app.services.moodle_client import MoodleClient
from app.routers.logs import append_log

router = APIRouter(prefix="/sync", tags=["Sincronización"])


@router.post("/moodle")
async def trigger_moodle_sync():
    """
    Ejecuta el ciclo de extracción y sincronización de calificaciones desde Moodle (HU-03).
    Registra el proceso en los logs del sistema (HU-16).
    """
    start_time = time.time()
    client = MoodleClient()
    conn_info = await client.test_connection()

    # Extracción de notas
    grades_mat1 = await client.get_course_grades(course_id=1)
    duration_ms = int((time.time() - start_time) * 1000)

    log_entry = append_log(
        tipo_proceso="SINCRONIZACION",
        estado="EXITO",
        mensaje=f"Sincronización completada en {duration_ms} ms. {len(grades_mat1)} registros procesados.",
        detalle={
            "curso": "MAT1",
            "modo": conn_info.get("modo"),
            "items_procesados": len(grades_mat1),
            "duplicados_evitados": 0
        }
    )

    return {
        "status": "success",
        "mensaje": "Sincronización completada exitosamente.",
        "duracion_ms": duration_ms,
        "detalles": conn_info,
        "registros_extraidos": len(grades_mat1),
        "log_id": log_entry["id"]
    }
