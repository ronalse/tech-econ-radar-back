"""
scripts/run_ingestion_cli.py

Ejecuta la ingesta directamente desde terminal, sin necesidad de
levantar el servidor FastAPI. Útil para pruebas manuales rápidas.

Uso (desde la carpeta back/):
    python scripts/run_ingestion_cli.py
"""

import sys
from pathlib import Path

# Permite importar los módulos de back/ (db, services, repositories)
# aunque este script viva en una subcarpeta.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from services.ingestion_service import run_ingestion  # noqa: E402


def main():
    summary = run_ingestion()
    for item in summary:
        if item["status"] == "success":
            print(
                f"{item['endpoint']}: Traídos {item['fetched']} | "
                f"Nuevos {item['new']} | Duplicados {item['duplicated']} | "
                f"Ruido {item['filtered_noise']}"
            )
        else:
            print(f"{item['endpoint']}: ERROR - {item['error']}")


if __name__ == "__main__":
    main()
