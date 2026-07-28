"""
routers/ingestion.py

Capa de FastAPI: define las rutas HTTP. NO contiene lógica de
negocio (eso vive en services/) ni SQL (eso vive en repositories/).
Solo recibe la petición, llama al service, y devuelve la respuesta.
"""

from fastapi import APIRouter, HTTPException

from services.ingestion_service import (
    format_remaining,
    get_time_until_next_update,
    run_ingestion,
)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/run")
def trigger_ingestion():
    """
    Dispara manualmente una corrida de ingesta (los 4 endpoints
    de Currents API). Tiene un cooldown de 1 hora desde la última
    corrida exitosa, para no saturar de peticiones a la API externa.
    La ingesta automática diaria (scheduler en main.py) corre aparte
    y no depende de este endpoint.
    """
    can_update, remaining = get_time_until_next_update()

    if not can_update:
        return {
            "status": "cooldown",
            "message": "Ya se ha actualizado",
            "next_update_in": format_remaining(remaining),
        }

    try:
        summary = run_ingestion()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "status": "updated",
        "message": "Ya se ha actualizado",
        "next_update_in": format_remaining(get_time_until_next_update()[1]),
        "summary": summary,
    }
