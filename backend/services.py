from __future__ import annotations

import logging
import time
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .database import get_connection
from .years import year_index
from hardcover.graphql_client import gql
from hardcover.queries import USER_BOOKS_BY_USERNAME_QUERY

logger = logging.getLogger("uvicorn.error")


BookMetadata = Dict[int, Dict[str, object]]


def _load_book_metadata() -> BookMetadata:
    query = """
        WITH filtered_genres AS (
            SELECT book_id, GROUP_CONCAT(genre, ', ') AS genres
            FROM book_genres
            WHERE tag_count > 2
            GROUP BY book_id
        )
        SELECT
            b.id,
            b.title,
            b.description,
            b.cover_url,
            b.cover_color,
            b.cover_w,
            b.cover_h,
            b.avg_rating,
            b.users_count,
            b.web_url,
            b.release_year,
            b.pages,
            COALESCE(aa.authors, '') AS authors,
            COALESCE(fg.genres, '') AS genres
        FROM books b
        LEFT JOIN book_author_agg aa ON aa.book_id = b.id
        LEFT JOIN filtered_genres fg ON fg.book_id = b.id
    """
    start = time.perf_counter()
    with get_connection() as conn:
        rows = conn.execute(query).fetchall()
    elapsed_ms = (time.perf_counter() - start) * 1000

    metadata: BookMetadata = {}
    for row in rows:
        authors = tuple(a for a in (row["authors"] or "").split(", ") if a)
        genres = tuple(g for g in (row["genres"] or "").split(", ") if g)
        metadata[row["id"]] = {
            "id": row["id"],
            "title": row["title"],
            "authors": authors,
            "description": row["description"],
            "cover_url": row["cover_url"],
            "cover_color": row["cover_color"],
            "cover_w": row["cover_w"],
            "cover_h": row["cover_h"],
            "avg_rating": row["avg_rating"],
            "users_count": row["users_count"],
            "web_url": row["web_url"],
            "release_year": row["release_year"],
            "pages": row["pages"],
            "genres": genres,
            "genre_set": {g.lower() for g in genres},
        }
    logger.info(
        "Loaded %d book metadata records into cache in %.1f ms",
        len(metadata),
        elapsed_ms,
    )
    return metadata


BOOK_METADATA = _load_book_metadata()


def fetch_book_details(
    book_ids: Iterable[int],
    required_genres: Optional[Set[str]] = None,
    decades: Optional[Set[str]] = None,
    exclude_unknown: bool = False,
) -> List[dict]:
    book_ids = list(dict.fromkeys(int(bid) for bid in book_ids))
    if not book_ids:
        return []

    details: List[dict] = []
    for bid in book_ids:
        cached = BOOK_METADATA.get(bid)
        if not cached:
            continue
        if required_genres and not required_genres.issubset(
            cached.get("genre_set", set())
        ):
            continue
        year = cached.get("release_year")
        year_match = True
        if decades:
            year_match = year_index.matches(bid, decades, False)
        if year_match and exclude_unknown and (year is None or year == 0):
            year_match = False
        if not year_match:
            continue

        details.append(
            {
                "id": cached["id"],
                "title": cached["title"],
                "authors": list(cached["authors"]),
                "description": cached["description"],
                "cover_url": cached["cover_url"],
                "cover_color": cached["cover_color"],
                "cover_w": cached["cover_w"],
                "cover_h": cached["cover_h"],
                "avg_rating": cached["avg_rating"],
                "users_count": cached["users_count"],
                "web_url": cached["web_url"],
                "release_year": cached["release_year"],
                "pages": cached["pages"],
                "genres": list(cached["genres"]),
            }
        )
    return details


def fetch_user_books(username: str) -> Tuple[str, List[int]]:
    normalized = username.strip()
    normalized = normalized.lstrip("@")
    if not normalized:
        return "", []

    start = time.perf_counter()
    data = gql(USER_BOOKS_BY_USERNAME_QUERY, {"username": normalized})
    elapsed_ms = (time.perf_counter() - start) * 1000

    book_ids: List[int] = []
    for entry in data.get("user_books", []):
        book = entry.get("book")
        if not book:
            continue
        try:
            book_ids.append(int(book["id"]))
        except (KeyError, TypeError, ValueError):
            continue

    logger.info(
        "Fetched %d bookshelf IDs for %s in %.1f ms",
        len(book_ids),
        normalized,
        elapsed_ms,
    )
    return normalized, book_ids
