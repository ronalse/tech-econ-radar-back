"""
routers/enrichment.py

POST /enrichment/run - procesa un lote de articulos pendientes
(is_processed = false) usando Gemini. Sin cooldown por ahora: el
volumen es bajo (docenas de articulos/dia) y el free tier de Gemini
(1500 peticiones/dia) tiene margen de sobra.
"""

from fastapi import APIRouter, HTTPException, Query

from services.enrichment_service import run_enrichment, backfill_missing_coordinates

router = APIRouter(prefix="/enrichment", tags=["enrichment"])


@router.post("/run")
def trigger_enrichment(batch_size: int = Query(20, ge=1, le=100)):
    try:
        summary = run_enrichment(batch_size=batch_size)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return summary


@router.post("/backfill-coordinates")
def trigger_backfill_coordinates():
    """
    Recalcula lat/lng de articulos ya procesados que se quedaron sin
    coordenadas (pais no estaba en la tabla en su momento). No llama
    al LLM - es instantaneo, se puede correr las veces que haga falta.
    """
    return backfill_missing_coordinates()
