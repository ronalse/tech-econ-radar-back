"""
services/filter_service.py

Lógica de negocio: qué filtros existen y cómo se calculan
para la UI. NO contiene SQL (eso vive en repositories/) ni sabe nada de FastAPI/HTTP entrante (eso vive en routers/).

"""
from repositories.articles_repository import get_filters_from_db
from db import get_connection

def get_filters():
    conn = get_connection()
    cur = conn.cursor()
    filters = get_filters_from_db(cur)
    cur.close()
    conn.close()
    return filters