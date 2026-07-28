"""
services/enrichment_service.py

Toma articulos con is_processed = false, le pide a Claude Haiku 4.5
que clasifique cada uno (categoria, pais, sentimiento, relevancia)
con salida JSON forzada via tool use, y guarda el resultado via el
repository. Las coordenadas (lat/lng) NO se le piden al LLM -- se
resuelven con la tabla fija de country_centroids.py.
"""

import os
import time
from datetime import datetime
from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from db import get_connection
from repositories.articles_repository import (
    get_articles_missing_coordinates,
    get_unprocessed_articles,
    update_article_enrichment,
    update_coordinates,
)
from services.country_centroids import get_country_coordinates

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL_NAME = "claude-haiku-4-5-20251001"

# Pausa corta entre articulos. El tier de pago de Anthropic tiene
# rate limits generosos desde el inicio, esto es solo un margen
# de cortesia, no una necesidad estricta como con el free tier de Gemini.
SECONDS_BETWEEN_CALLS = 2
RETRY_WAIT_ON_429 = 30

CATEGORIES = ["ai", "funding", "cybersecurity", "hardware", "macro_economy", "markets", "other"]
SENTIMENTS = ["positive", "neutral", "negative"]

CLASSIFY_TOOL = {
    "name": "classify_article",
    "description": "Clasifica una noticia de tecnologia/economia con categoria, pais, sentimiento y relevancia.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": CATEGORIES,
                "description": "La categoria que mejor encaje con la noticia.",
            },
            "country_code": {
                "type": "string",
                "description": (
                    "Codigo de pais ISO 3166-1 alpha-2 (ej. US, GB, DE) del pais "
                    "mas relevante para la noticia (donde ocurre o donde esta la "
                    "empresa/entidad principal). Si es una noticia global o no se "
                    "puede determinar un pais claro, usa 'XX'."
                ),
            },
            "sentiment": {
                "type": "string",
                "enum": SENTIMENTS,
                "description": "Tono de la noticia para la industria.",
            },
            "relevance_score": {
                "type": "number",
                "description": (
                    "De 0.0 a 1.0, que tan significativa es esta noticia para "
                    "alguien que sigue tecnologia y economia de cerca."
                ),
            },
        },
        "required": ["category", "country_code", "sentiment", "relevance_score"],
    },
}


class ArticleClassification(BaseModel):
    category: Literal["ai", "funding", "cybersecurity", "hardware", "macro_economy", "markets", "other"]
    country_code: str
    sentiment: Literal["positive", "neutral", "negative"]
    relevance_score: float


def _log(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def classify_article(client: anthropic.Anthropic, title: str, description: str) -> ArticleClassification:
    prompt = (
        f"Clasifica la siguiente noticia de tecnologia/economia.\n\n"
        f"Titulo: {title}\n"
        f"Descripcion: {description or '(sin descripcion)'}"
    )

    for attempt in range(2):
        try:
            response = client.messages.create(
                model=MODEL_NAME,
                max_tokens=300,
                tools=[CLASSIFY_TOOL],
                tool_choice={"type": "tool", "name": "classify_article"},
                messages=[{"role": "user", "content": prompt}],
            )
            tool_block = next(b for b in response.content if b.type == "tool_use")
            return ArticleClassification(**tool_block.input)
        except anthropic.RateLimitError:
            if attempt == 0:
                _log(f"    429 recibido, esperando {RETRY_WAIT_ON_429}s antes de reintentar...")
                time.sleep(RETRY_WAIT_ON_429)
                continue
            raise


def backfill_missing_coordinates() -> dict:
    """
    Recalcula lat/lng para articulos ya procesados que se quedaron
    sin coordenadas (pais no estaba en la tabla en su momento).
    No llama al LLM, no gasta cuota, es instantaneo.
    """
    conn = get_connection()
    cur = conn.cursor()

    pending = get_articles_missing_coordinates(cur)
    updated = 0
    still_missing = 0

    for article in pending:
        lat, lng = get_country_coordinates(article["country_code"])
        if lat is not None:
            update_coordinates(cur, article["id"], lat, lng)
            updated += 1
        else:
            still_missing += 1

    conn.commit()
    cur.close()
    conn.close()

    return {
        "candidates": len(pending),
        "updated": updated,
        "still_missing": still_missing,
    }


def run_enrichment(batch_size: int = 20) -> dict:
    """
    Procesa hasta batch_size articulos pendientes. Devuelve un resumen
    con cuantos se procesaron y cuantos fallaron.
    """
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "pega_aqui_tu_anthropic_key":
        raise RuntimeError("Falta configurar ANTHROPIC_API_KEY en back/.env")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    conn = get_connection()
    cur = conn.cursor()

    articles = get_unprocessed_articles(cur, limit=batch_size)
    total = len(articles)
    processed = 0
    failed = 0
    errors = []

    for index, article in enumerate(articles, start=1):
        _log(f"[{index}/{total}] procesando: {article['title'][:70]}")
        try:
            result = classify_article(client, article["title"], article["description"])
            lat, lng = get_country_coordinates(result.country_code)

            update_article_enrichment(
                cur,
                article_id=article["id"],
                category=result.category,
                country_code=None if result.country_code == "XX" else result.country_code,
                lat=lat,
                lng=lng,
                sentiment=result.sentiment,
                relevance_score=result.relevance_score,
            )
            conn.commit()
            processed += 1
            _log(f"    -> OK: {result.category} | {result.country_code} | {result.sentiment} | relevancia {result.relevance_score}")
        except Exception as exc:
            conn.rollback()
            failed += 1
            errors.append({"article_id": str(article["id"]), "error": str(exc)})
            _log(f"    -> ERROR: {exc}")

        _log(f"    esperando {SECONDS_BETWEEN_CALLS}s...")
        time.sleep(SECONDS_BETWEEN_CALLS)

    cur.close()
    conn.close()

    return {
        "candidates": len(articles),
        "processed": processed,
        "failed": failed,
        "errors": errors,
    }
