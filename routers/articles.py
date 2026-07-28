"""
routers/articles.py

GET /articles con paginación simple (limit/offset). Sin filtros por
ahora — se añadirán más adelante cuando la Fase 2 (enriquecimiento
con IA) tenga category/sentiment/country_code poblados de verdad.
"""

from fastapi import APIRouter, Query

from services.articles_service import list_articles

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("")
def get_articles_endpoint(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return list_articles(limit, offset)
