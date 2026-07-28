"""
repositories/articles_repository.py

ÚNICA capa que escribe SQL directo. Ni el router ni el service
deben construir queries — todo pasa por aquí. Si mañana cambias
de Postgres a otra base, solo tocas este archivo.
"""


def insert_article(cur, article: dict, is_noise: bool) -> bool:
    """
    Inserta un artículo. Devuelve True si fue insertado (nuevo),
    False si ya existía (duplicado por url, gracias al UNIQUE del schema).
    """
    cur.execute(
        """
        INSERT INTO articles (
            external_id, title, description, url, author,
            image_url, language, published_at, raw_category, is_noise
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (url) DO NOTHING
        RETURNING id;
        """,
        (
            article.get("id"),
            article.get("title"),
            article.get("description"),
            article.get("url"),
            article.get("author") or None,
            article.get("image") if article.get("image") != "None" else None,
            article.get("language", "en"),
            article.get("published"),
            article.get("category", []),
            is_noise,
        ),
    )
    return cur.fetchone() is not None


def get_articles_missing_coordinates(cur):
    """
    Articulos ya procesados que tienen country_code pero se quedaron
    sin lat/lng (porque el pais no estaba en la tabla de centroides
    en el momento en que se procesaron). Sirve para backfill sin
    tener que volver a llamar al LLM.
    """
    cur.execute(
        """
        SELECT id, country_code FROM articles
        WHERE is_processed = true AND country_code IS NOT NULL AND lat IS NULL;
        """
    )
    colnames = [desc[0] for desc in cur.description]
    return [dict(zip(colnames, row)) for row in cur.fetchall()]


def update_coordinates(cur, article_id: str, lat: float, lng: float) -> None:
    cur.execute(
        "UPDATE articles SET lat = %s, lng = %s WHERE id = %s;",
        (lat, lng, article_id),
    )


def get_unprocessed_articles(cur, limit: int = 20):
    """
    Devuelve articulos con is_processed = false, listos para enviar
    al LLM. Se excluyen los marcados como ruido: no vale la pena
    gastar tokens clasificando contenido que ya sabemos descartar.
    """
    cur.execute(
        """
        SELECT id, title, description
        FROM articles
        WHERE is_processed = false AND is_noise = false
        ORDER BY published_at DESC
        LIMIT %s;
        """,
        (limit,),
    )
    colnames = [desc[0] for desc in cur.description]
    return [dict(zip(colnames, row)) for row in cur.fetchall()]


def update_article_enrichment(
    cur,
    article_id: str,
    category: str,
    country_code: str | None,
    lat: float | None,
    lng: float | None,
    sentiment: str,
    relevance_score: float,
) -> None:
    cur.execute(
        """
        UPDATE articles
        SET category = %s,
            country_code = %s,
            lat = %s,
            lng = %s,
            sentiment = %s,
            relevance_score = %s,
            is_processed = true
        WHERE id = %s;
        """,
        (category, country_code, lat, lng, sentiment, relevance_score, article_id),
    )


def get_last_ingestion_finished_at(cur):
    """
    Devuelve la fecha/hora (UTC) en que terminó la última corrida
    exitosa de ingesta, o None si nunca se ha ejecutado ninguna.
    Se usa para aplicar el cooldown de 1 hora en el POST manual.
    """
    cur.execute(
        "SELECT MAX(finished_at) FROM ingestion_runs WHERE status = 'success';"
    )
    row = cur.fetchone()
    return row[0] if row else None


def get_articles(cur, limit: int, offset: int):
    """
    Devuelve (lista_de_articulos, total). Sin filtros por ahora,
    solo excluye ruido (is_noise) y pagina con limit/offset.
    Cuando se agreguen filtros mas adelante, vuelven aqui.
    """
    cur.execute(
        """
        SELECT id, external_id, title, description, url, author,
               image_url, language, published_at, category,
               country_code, lat, lng, sentiment, relevance_score,
               is_processed, is_noise
        FROM articles
        WHERE is_noise = false
        ORDER BY published_at DESC
        LIMIT %s OFFSET %s;
        """,
        (limit, offset),
    )
    colnames = [desc[0] for desc in cur.description]
    rows = [dict(zip(colnames, row)) for row in cur.fetchall()]

    cur.execute("SELECT COUNT(*) FROM articles WHERE is_noise = false;")
    total = cur.fetchone()[0]

    return rows, total


def insert_ingestion_run(
    cur,
    run_id: str,
    source_endpoint: str,
    query_params: str,
    status: str,
    articles_fetched: int = 0,
    articles_new: int = 0,
    articles_duplicated: int = 0,
    articles_filtered: int = 0,
    error_message: str | None = None,
) -> None:
    cur.execute(
        """
        INSERT INTO ingestion_runs (
            id, source_endpoint, query_params, finished_at,
            articles_fetched, articles_new, articles_duplicated,
            articles_filtered, status, error_message
        )
        VALUES (%s, %s, %s, now(), %s, %s, %s, %s, %s, %s);
        """,
        (
            run_id,
            source_endpoint,
            query_params,
            articles_fetched,
            articles_new,
            articles_duplicated,
            articles_filtered,
            status,
            error_message,
        ),
    )

def get_filters_from_db(cur):
    """
    Devuelve la lista de filtros que la UI puede mostrar para que el usuario seleccione.
    Los sacamos de la tabla de articulos (category, country_code, sentiment)
    de manera que la UI no tenga que hardcodear nada, y siempre refleje
    la realidad de lo que hay en la base de datos.

    Cada filtro viene como lista de {clave: valor, count: N}, agrupado
    y contado en SQL (GROUP BY ya elimina los repetidos por si solo).
    """

    cur.execute(
        """
        SELECT category, COUNT(*) FROM articles
        WHERE category IS NOT NULL
        GROUP BY category
        ORDER BY COUNT(*) DESC;
        """
    )
    categories = [{"category": row[0], "count": row[1]} for row in cur.fetchall()]

    cur.execute(
        """
        SELECT country_code, COUNT(*) FROM articles
        WHERE country_code IS NOT NULL
        GROUP BY country_code
        ORDER BY COUNT(*) DESC;
        """
    )
    country_codes = [{"country_code": row[0], "count": row[1]} for row in cur.fetchall()]

    cur.execute(
        """
        SELECT sentiment, COUNT(*) FROM articles
        WHERE sentiment IS NOT NULL
        GROUP BY sentiment
        ORDER BY COUNT(*) DESC;
        """
    )
    sentiments = [{"sentiment": row[0], "count": row[1]} for row in cur.fetchall()]

    return {
        "categories": categories,
        "country_codes": country_codes,
        "sentiments": sentiments,
    }