import re
from typing import List

from .database import get_connection

MAX_QUERY_TOKENS = 8
MAX_TOKEN_LENGTH = 32


def _normalize_query(query: str) -> str:
    tokens = re.findall(r"[\w]+", query.lower())
    tokens = [token[:MAX_TOKEN_LENGTH] for token in tokens[:MAX_QUERY_TOKENS]]
    if not tokens:
        return ""
    return " AND ".join(f'"{token}"' for token in tokens)


def _split_list(value: str | None) -> List[str]:
    if not value:
        return []
    return [part for part in value.split(", ") if part]


def _row_to_summary(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "authors": _split_list(row["authors"]),
        "genres": _split_list(row["genres"]),
        "cover_url": row["cover_url"],
        "avg_rating": row["avg_rating"],
        "users_count": row["users_count"],
        "web_url": row["web_url"],
    }


def _fallback_search(conn, query: str, limit: int):
    like = f"%{query.lower()}%"
    return conn.execute(
        """
        WITH filtered_genres AS (
            SELECT book_id, GROUP_CONCAT(genre, ', ') AS genres
            FROM book_genres
            WHERE tag_count > 2
            GROUP BY book_id
        )
        SELECT
            b.id,
            b.title,
            COALESCE(aa.authors, '') AS authors,
            COALESCE(fg.genres, '') AS genres,
            b.cover_url,
            b.avg_rating,
            b.users_count,
            b.web_url
        FROM books b
        LEFT JOIN book_author_agg aa ON aa.book_id = b.id
        LEFT JOIN filtered_genres fg ON fg.book_id = b.id
        WHERE LOWER(b.title) LIKE ?
           OR LOWER(COALESCE(aa.authors, '')) LIKE ?
           OR LOWER(COALESCE(fg.genres, '')) LIKE ?
        ORDER BY b.users_count DESC
        LIMIT ?
        """,
        (like, like, like, limit),
    ).fetchall()


def search_books(query: str, limit: int) -> List[dict]:
    query = query.strip()
    normalized = _normalize_query(query)
    genre_cte = """
        WITH filtered_genres AS (
            SELECT book_id, GROUP_CONCAT(genre, ', ') AS genres
            FROM book_genres
            WHERE tag_count > 2
            GROUP BY book_id
        )
    """
    with get_connection() as conn:
        if normalized:
            rows = conn.execute(
                f"""
                {genre_cte}
                SELECT
                    b.id,
                    b.title,
                    COALESCE(aa.authors, '') AS authors,
                    COALESCE(fg.genres, '') AS genres,
                    b.cover_url,
                    b.avg_rating,
                    b.users_count,
                    b.web_url
                FROM book_search
                JOIN books b ON b.id = book_search.rowid
                LEFT JOIN book_author_agg aa ON aa.book_id = b.id
                LEFT JOIN filtered_genres fg ON fg.book_id = b.id
                WHERE book_search MATCH ?
                ORDER BY bm25(book_search), b.users_count DESC
                LIMIT ?
                """,
                (normalized, limit),
            ).fetchall()
            if not rows:
                rows = _fallback_search(conn, query, limit)
        else:
            rows = conn.execute(
                f"""
                {genre_cte}
                SELECT
                    b.id,
                    b.title,
                    COALESCE(aa.authors, '') AS authors,
                    COALESCE(fg.genres, '') AS genres,
                    b.cover_url,
                    b.avg_rating,
                    b.users_count,
                    b.web_url
                FROM books b
                LEFT JOIN book_author_agg aa ON aa.book_id = b.id
                LEFT JOIN filtered_genres fg ON fg.book_id = b.id
                ORDER BY b.users_count DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [_row_to_summary(row) for row in rows]
