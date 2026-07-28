"""
services/ingestion_service.py

Lógica de negocio: qué endpoints llamar, cómo decidir si un
artículo es ruido, y cómo orquestar la llamada a la API +
la inserción vía el repository. NO contiene SQL (eso vive en
repositories/) ni sabe nada de FastAPI/HTTP entrante (eso vive
en routers/).
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

from db import get_connection
from repositories.articles_repository import (
    get_last_ingestion_finished_at,
    insert_article,
    insert_ingestion_run,
)

load_dotenv()

# Tiempo mínimo entre corridas manuales (POST /ingestion/run),
# para no saturar de peticiones a Currents API.
MIN_UPDATE_INTERVAL = timedelta(hours=1)

API_KEY = os.getenv("CURRENTS_API_KEY")
BASE_URL = "https://api.currentsapi.services/v2"

ENDPOINTS = [
    {
        "name": "latest-news-tech",
        "url": f"{BASE_URL}/latest-news",
        "params": {"category": "science_technology", "language": "en", "page_size": 20},
    },
    {
        "name": "search-ai",
        "url": f"{BASE_URL}/search",
        "params": {"keywords": "artificial intelligence", "language": "en", "page_size": 20},
    },
    {
        "name": "search-funding",
        "url": f"{BASE_URL}/search",
        "params": {"keywords": "funding startup", "language": "en", "page_size": 20},
    },
    {
        "name": "search-economy",
        "url": f"{BASE_URL}/search",
        "params": {"keywords": "inflation economy", "language": "en", "page_size": 20},
    },
]

NOISE_DOMAINS = ["reddit.com", "github.com"]


def is_noise(article: dict) -> bool:
    url = article.get("url", "")
    description = article.get("description", "") or ""
    if any(domain in url for domain in NOISE_DOMAINS):
        return True
    if len(description.strip()) < 20:
        return True
    return False


def fetch_endpoint(endpoint: dict) -> list[dict]:
    params = dict(endpoint["params"])
    params["apiKey"] = API_KEY
    response = requests.get(endpoint["url"], params=params, timeout=15)
    if response.status_code != 200:
        print(f"  Respuesta cruda del servidor ({response.status_code}): {response.text}")
    response.raise_for_status()
    data = response.json()
    return data.get("news", [])


def run_ingestion() -> list[dict]:
    """
    Ejecuta la ingesta completa: llama a los 4 endpoints, inserta
    artículos nuevos, registra cada corrida en ingestion_runs.
    Devuelve un resumen por endpoint (útil para loguear o exponer vía API).
    """
    if not API_KEY :
        raise RuntimeError("Falta configurar CURRENTS_API_KEY en back/.env")

    conn = get_connection()
    cur = conn.cursor()
    summary = []

    for endpoint in ENDPOINTS:
        try:
            articles = fetch_endpoint(endpoint)
        except requests.RequestException as exc:
            insert_ingestion_run(
                cur,
                run_id=str(uuid.uuid4()),
                source_endpoint=endpoint["name"],
                query_params=json.dumps(endpoint["params"]),
                status="error",
                error_message=str(exc),
            )
            conn.commit()
            summary.append({"endpoint": endpoint["name"], "status": "error", "error": str(exc)})
            continue

        fetched = len(articles)
        new_count = 0
        duplicated_count = 0
        filtered_count = 0

        for article in articles:
            noise = is_noise(article)
            if noise:
                filtered_count += 1
            inserted = insert_article(cur, article, noise)
            if inserted:
                new_count += 1
            else:
                duplicated_count += 1

        insert_ingestion_run(
            cur,
            run_id=str(uuid.uuid4()),
            source_endpoint=endpoint["name"],
            query_params=json.dumps(endpoint["params"]),
            status="success",
            articles_fetched=fetched,
            articles_new=new_count,
            articles_duplicated=duplicated_count,
            articles_filtered=filtered_count,
        )
        conn.commit()

        summary.append(
            {
                "endpoint": endpoint["name"],
                "status": "success",
                "fetched": fetched,
                "new": new_count,
                "duplicated": duplicated_count,
                "filtered_noise": filtered_count,
            }
        )

    cur.close()
    conn.close()
    return summary


def get_time_until_next_update() -> tuple[bool, timedelta]:
    """
    Consulta cuándo terminó la última corrida exitosa y calcula si ya
    pasó el tiempo mínimo (MIN_UPDATE_INTERVAL) para permitir otra.

    Devuelve (puede_actualizar: bool, tiempo_restante: timedelta).
    Si puede_actualizar es True, tiempo_restante es timedelta(0).
    """
    conn = get_connection()
    cur = conn.cursor()
    last_finished_at = get_last_ingestion_finished_at(cur)
    cur.close()
    conn.close()

    if last_finished_at is None:
        return True, timedelta(0)

    now = datetime.now(timezone.utc)
    elapsed = now - last_finished_at

    if elapsed >= MIN_UPDATE_INTERVAL:
        return True, timedelta(0)

    remaining = MIN_UPDATE_INTERVAL - elapsed
    return False, remaining


def format_remaining(remaining: timedelta) -> str:
    total_seconds = int(remaining.total_seconds())
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes} min {seconds} s"
