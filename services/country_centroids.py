"""
services/country_centroids.py

Tabla de centroides (lat, lng) por pais (ISO 3166-1 alpha-2).
El LLM solo nos dice el pais; nosotros resolvemos las coordenadas
aqui, en vez de pedirle al modelo que "invente" numeros precisos
de latitud/longitud.

"XX" (o un codigo no listado) deja lat/lng en None - el articulo
simplemente no se pinta en el mapa (pero si en el feed/listado).
"""

COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "US": (39.8283, -98.5795), "GB": (55.3781, -3.4360), "DE": (51.1657, 10.4515),
    "FR": (46.2276, 2.2137), "ES": (40.4637, -3.7492), "IT": (41.8719, 12.5674),
    "NL": (52.1326, 5.2913), "IE": (53.4129, -8.2439), "SE": (60.1282, 18.6435),
    "NO": (60.4720, 8.4689), "DK": (56.2639, 9.5018), "FI": (61.9241, 25.7482),
    "CH": (46.8182, 8.2275), "AT": (47.5162, 14.5501), "BE": (50.5039, 4.4699),
    "PT": (39.3999, -8.2245), "PL": (51.9194, 19.1451), "CZ": (49.8175, 15.4730),
    "GR": (39.0742, 21.8243), "RO": (45.9432, 24.9668), "HU": (47.1625, 19.5033),
    "UA": (48.3794, 31.1656), "TR": (38.9637, 35.2433),

    "CN": (35.8617, 104.1954), "JP": (36.2048, 138.2529), "KR": (35.9078, 127.7669),
    "IN": (20.5937, 78.9629), "PK": (30.3753, 69.3451), "BD": (23.6850, 90.3563),
    "SG": (1.3521, 103.8198), "MY": (4.2105, 101.9758), "ID": (-0.7893, 113.9213),
    "TH": (15.8700, 100.9925), "VN": (14.0583, 108.2772), "PH": (12.8797, 121.7740),
    "TW": (23.6978, 120.9605), "HK": (22.3193, 114.1694), "SA": (23.8859, 45.0792),
    "AE": (23.4241, 53.8478), "IL": (31.0461, 34.8516), "IR": (32.4279, 53.6880),
    "IQ": (33.2232, 43.6793), "QA": (25.3548, 51.1839), "KW": (29.3117, 47.4818),

    "CA": (56.1304, -106.3468), "MX": (23.6345, -102.5528), "BR": (-14.2350, -51.9253),
    "AR": (-38.4161, -63.6167), "CL": (-35.6751, -71.5430), "CO": (4.5709, -74.2973),
    "PE": (-9.1900, -75.0152), "VE": (6.4238, -66.5897), "UY": (-32.5228, -55.7658),

    "AU": (-25.2744, 133.7751), "NZ": (-40.9006, 174.8860),

    "RU": (61.5240, 105.3188), "ZA": (-30.5595, 22.9375), "NG": (9.0820, 8.6753),
    "EG": (26.8206, 30.8025), "KE": (-0.0236, 37.9062), "MA": (31.7917, -7.0926),
    "GH": (7.9465, -1.0232), "ET": (9.1450, 40.4897),

    "XX": (None, None),
}


def get_country_coordinates(country_code: str | None) -> tuple[float | None, float | None]:
    if not country_code:
        return None, None
    entry = COUNTRY_CENTROIDS.get(country_code.upper())
    if entry is None:
        # Pais no listado todavia: se guarda el country_code igual,
        # pero sin coordenadas (no rompe nada, solo no aparece en el mapa)
        print(f"[country_centroids] Pais no encontrado en la tabla: {country_code}")
        return None, None
    return entry
