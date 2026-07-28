"""
main.py

Punto de entrada de la aplicación FastAPI. Arma la app, conecta
los routers, y arranca un scheduler en segundo plano que ejecuta
la ingesta automáticamente una vez al día — el usuario NO necesita
llamar al POST para que los datos se actualicen.

El POST /ingestion/run sigue disponible aparte, para que el usuario
fuerce una actualización manual (con su propio cooldown de 1 hora).

Para levantar el servidor:
    uvicorn main:app --reload
"""

from contextlib import asynccontextmanager
import os

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import articles, enrichment, ingestion, filters
from services.enrichment_service import run_enrichment
from services.ingestion_service import run_ingestion

# En Render, configura la variable de entorno ENVIRONMENT=production.
# Localmente, si no existe, se asume development y los docs quedan visibles.
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"


scheduler = BackgroundScheduler(timezone="UTC")


def scheduled_ingestion_job():
    print("[scheduler] Ejecutando ingesta automática diaria...")
    try:
        summary = run_ingestion()
        print(f"[scheduler] Ingesta completada: {summary}")
    except Exception as exc:
        print(f"[scheduler] Error en la ingesta automática: {exc}")
        return

    print("[scheduler] Ejecutando enriquecimiento con IA...")
    try:
        enrich_summary = run_enrichment(batch_size=100)
        print(f"[scheduler] Enriquecimiento completado: {enrich_summary}")
    except Exception as exc:
        print(f"[scheduler] Error en el enriquecimiento: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Arranca al iniciar la app: corre una vez ahora, y luego cada 24h.
    scheduler.add_job(scheduled_ingestion_job, "interval", hours=24)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="Tech/Econ Radar API",
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# Permite que el frontend (Next.js en localhost:3000) llame a esta API.
# Sin esto, el navegador bloquea las respuestas aunque el servidor
# responda 200 - por eso los logs de uvicorn se ven bien pero el
# fetch() falla en el navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://tech-econ-radar-front.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(articles.router)
app.include_router(enrichment.router)
app.include_router(ingestion.router)
app.include_router(filters.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
