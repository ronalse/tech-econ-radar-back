"""
routers/filters.py

Devuelve la lista de filtros que la UI puede mostrar para que el
usuario seleccione. Los sacamos de la tabla de articulos (category,
country_code, sentiment) de manera que la UI no tenga que
hardcodear nada, y siempre refleje la realidad de la base de datos.
"""

from fastapi import APIRouter

from services.filter_service import get_filters

router = APIRouter(prefix="/filters", tags=["filters"])


@router.get("/get_all")
def list_filters():
    return get_filters()
