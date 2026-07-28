"""
scripts/run_enrichment_cli.py

Procesa TODOS los artículos pendientes (is_processed = false), uno
por uno, respetando el rate limit de Gemini (13s entre cada uno).
Pensado para correr en terminal sin depender de un navegador que
corte la conexión por timeout con lotes grandes.

Uso (desde la carpeta back/):
    python scripts/run_enrichment_cli.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from services.enrichment_service import run_enrichment  # noqa: E402

# Suficientemente alto para cubrir cualquier backlog acumulado.
MAX_BACKLOG = 5000


def main():
    print("Vaciando backlog de artículos sin enriquecer...\n")
    summary = run_enrichment(batch_size=MAX_BACKLOG)

    print("\n--- Resumen ---")
    print(f"Candidatos encontrados: {summary['candidates']}")
    print(f"Procesados con éxito:  {summary['processed']}")
    print(f"Fallidos:              {summary['failed']}")

    if summary["failed"]:
        print("\nDetalle de errores:")
        for err in summary["errors"]:
            print(f"  - {err['article_id']}: {err['error'][:120]}")


if __name__ == "__main__":
    main()
