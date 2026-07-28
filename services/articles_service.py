"""
services/articles_service.py

Lógica de negocio para CONSULTAR artículos (lectura). Separado de
ingestion_service.py porque es una responsabilidad distinta: aquel
trae datos desde afuera, este los sirve hacia afuera.
"""

from db import get_connection
from repositories.articles_repository import get_articles


def list_articles(limit: int, offset: int) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    rows, total = get_articles(cur, limit, offset)
    cur.close()
    conn.close()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": rows,
    }
