from __future__ import annotations

import logging
import re
import time
from typing import List, Optional, Set

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import get_connection
from .genres import genre_index
from .recommender import recommender
from .schemas import (
    BookSummary,
    RecommendRequest,
    RecommendResponse,
    RecommendedBook,
    UserBooksResponse,
)
from .search import search_books
from .services import fetch_book_details, fetch_user_books
from .years import year_index

settings = get_settings()
MAX_RECOMMEND_LOOPS = 200
MAX_FILTER_LENGTH = 50
MAX_USERNAME_LENGTH = 64
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
VALID_DECADE_IDS = {opt.id for opt in year_index.available_decades()}

app = FastAPI(title="Book Recommendations API")
logger = logging.getLogger("uvicorn.error")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _shorten_description(text: str | None, limit: int = 400) -> str | None:
    if not text:
        return None
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    shortened = stripped[:limit].rsplit(" ", 1)[0]
    return shortened + "…"


def _normalize_filter_values(
    values: list[str],
    *,
    field_name: str,
    allowed: Set[str] | None = None,
) -> Set[str]:
    normalized: Set[str] = set()
    for value in values:
        cleaned = value.strip().lower()
        if not cleaned:
            continue
        if len(cleaned) > MAX_FILTER_LENGTH:
            raise HTTPException(
                status_code=422,
                detail=f"{field_name} values must be {MAX_FILTER_LENGTH} characters or fewer",
            )
        if allowed is not None and cleaned not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported {field_name} value: {value}",
            )
        normalized.add(cleaned)
    return normalized


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search", response_model=List[BookSummary])
def search(
    q: str = Query("", max_length=120),
    limit: int = Query(10, ge=1, le=50),
):
    limit = max(1, min(limit, settings.max_page_size))
    return search_books(q, limit)


@app.post("/recommend", response_model=RecommendResponse)
def recommend(payload: RecommendRequest):
    handler_start = time.perf_counter()
    required_genres = _normalize_filter_values(payload.genres, field_name="genre")
    required_decades = _normalize_filter_values(
        payload.decades,
        field_name="decade",
        allowed=VALID_DECADE_IDS,
    )
    exclude_unknown = payload.exclude_unknown_years
    desired_total = payload.offset + payload.limit
    collected: List[RecommendedBook] = []
    raw_offset = 0
    chunk_size = max(payload.limit * 3, 50)
    book_ids = [int(bid) for bid in payload.book_ids]
    exclude_book_ids: Set[int] = {int(bid) for bid in payload.exclude_book_ids}
    genre_whitelist: Optional[Set[int]] = None
    if required_genres:
        genre_whitelist = genre_index.candidate_ids(required_genres)
        if genre_whitelist is not None:
            if required_decades or exclude_unknown:
                genre_whitelist = {
                    bid
                    for bid in genre_whitelist
                    if year_index.matches(bid, required_decades, exclude_unknown)
                }
            if len(genre_whitelist) == 0:
                return RecommendResponse(results=[], count=0, next_offset=0)

    year_whitelist: Optional[Set[int]] = None
    if genre_whitelist is None:
        year_whitelist = year_index.candidate_ids(required_decades, exclude_unknown)
        if year_whitelist is not None and len(year_whitelist) == 0:
            return RecommendResponse(results=[], count=0, next_offset=0)

    candidate_whitelist: Optional[Set[int]] = None
    if genre_whitelist is not None:
        candidate_whitelist = set(genre_whitelist)
    elif year_whitelist is not None:
        candidate_whitelist = set(year_whitelist)

    if candidate_whitelist is not None and exclude_book_ids:
        candidate_whitelist.difference_update(exclude_book_ids)
        if len(candidate_whitelist) == 0:
            return RecommendResponse(results=[], count=0, next_offset=payload.offset)

    aborted_for_limit = False
    try:
        total_candidates = None
        loop_idx = 0
        while len(collected) < desired_total + 1:
            if loop_idx >= MAX_RECOMMEND_LOOPS:
                aborted_for_limit = True
                logger.info(
                    "Recommend loop aborted after %d iterations (genres=%s, decades=%s, exclude_unknown=%s)",
                    loop_idx,
                    ", ".join(sorted(required_genres)) if required_genres else "all",
                    ", ".join(sorted(required_decades)) if required_decades else "all",
                    exclude_unknown,
                )
                break
            loop_idx += 1
            loop_start = time.perf_counter()
            rec_fetch_start = loop_start
            recs_chunk, total, rec_timings = recommender.recommend(
                book_ids,
                limit=chunk_size,
                offset=raw_offset,
                exclude_book_ids=exclude_book_ids,
            )
            rec_fetch_ms = (time.perf_counter() - rec_fetch_start) * 1000
            if total_candidates is None:
                total_candidates = total
            if not recs_chunk:
                break
            raw_offset += len(recs_chunk)

            filtered_ids = []
            for rec in recs_chunk:
                if rec.book_id in exclude_book_ids:
                    continue
                passes = True
                if candidate_whitelist is not None:
                    if rec.book_id not in candidate_whitelist:
                        passes = False
                else:
                    if required_genres and not genre_index.matches(
                        rec.book_id, required_genres
                    ):
                        passes = False
                    if passes and (required_decades or exclude_unknown):
                        if not year_index.matches(
                            rec.book_id, required_decades, exclude_unknown
                        ):
                            passes = False
                if passes:
                    filtered_ids.append(rec.book_id)

            chunk_ids = filtered_ids

            if (required_genres or required_decades or exclude_unknown) and not chunk_ids:
                detail_fetch_ms = 0.0
                logger.info(
                    (
                        "Recommend loop %d: chunk=%d recs (%.1f ms pseudo=%.1f ms, score=%.1f ms), "
                        "details skipped (0 matches), collected=%d/%d (genres=%s, decades=%s, exclude_unknown=%s)"
                    ),
                    loop_idx,
                    len(recs_chunk),
                    rec_fetch_ms,
                    rec_timings.get("pseudo_ms", 0.0),
                    rec_timings.get("scoring_ms", 0.0),
                    len(collected),
                    desired_total + 1,
                    ", ".join(sorted(required_genres)) if required_genres else "all",
                    ", ".join(sorted(required_decades)) if required_decades else "all",
                    exclude_unknown,
                )
                continue

            detail_fetch_start = time.perf_counter()
            details = fetch_book_details(
                chunk_ids,
                required_genres if required_genres else None,
                required_decades if required_decades else None,
                exclude_unknown,
            )
            detail_fetch_ms = (time.perf_counter() - detail_fetch_start) * 1000
            detail_map = {item["id"]: item for item in details}

            for rec in recs_chunk:
                detail = detail_map.get(rec.book_id)
                if not detail:
                    continue
                collected.append(
                    RecommendedBook(
                        id=detail["id"],
                        title=detail["title"],
                        authors=detail["authors"],
                        description=_shorten_description(detail["description"]),
                        cover_url=detail["cover_url"],
                        avg_rating=detail["avg_rating"],
                        users_count=detail["users_count"],
                        web_url=detail["web_url"],
                        release_year=detail["release_year"],
                        pages=detail["pages"],
                        genres=detail["genres"],
                        score=rec.score,
                    )
                )
                if len(collected) >= desired_total + 1:
                    break

            if total_candidates is not None and raw_offset >= total_candidates:
                break

            loop_ms = (time.perf_counter() - loop_start) * 1000
            logger.info(
                (
                    "Recommend loop %d: chunk=%d recs (%.1f ms pseudo=%.1f ms, score=%.1f ms), "
                    "details=%d (%.1f ms), collected=%d/%d (genres=%s, decades=%s, exclude_unknown=%s)"
                ),
                loop_idx,
                len(recs_chunk),
                rec_fetch_ms,
                rec_timings.get("pseudo_ms", 0.0),
                rec_timings.get("scoring_ms", 0.0),
                len(details),
                detail_fetch_ms,
                len(collected),
                desired_total + 1,
                ", ".join(sorted(required_genres)) if required_genres else "all",
                ", ".join(sorted(required_decades)) if required_decades else "all",
                exclude_unknown,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    slice_start = min(payload.offset, len(collected))
    slice_end = min(slice_start + payload.limit, len(collected))
    results = collected[slice_start:slice_end]
    has_more = len(collected) > slice_end
    if aborted_for_limit:
        has_more = False
    next_offset = slice_end
    count = slice_end + (1 if has_more else 0)
    if aborted_for_limit and not results:
        return RecommendResponse(results=[], count=0, next_offset=payload.offset)

    total_ms = (time.perf_counter() - handler_start) * 1000
    logger.info(
        "Recommend handler completed in %.1f ms (returned=%d, offset=%d, limit=%d, genres=%s, decades=%s, exclude_unknown=%s)",
        total_ms,
        len(results),
        payload.offset,
        payload.limit,
        ", ".join(sorted(required_genres)) if required_genres else "all",
        ", ".join(sorted(required_decades)) if required_decades else "all",
        exclude_unknown,
    )

    return RecommendResponse(results=results, count=count, next_offset=next_offset)


@app.get("/genres", response_model=List[str])
def genres(limit: int = Query(50, ge=1, le=200)):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT genre
            FROM (
                SELECT genre, SUM(tag_count) AS freq
                FROM book_genres
                WHERE tag_count > 2
                GROUP BY genre
            )
            ORDER BY freq DESC, genre ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [row["genre"] for row in rows]


@app.get("/decades")
def decades():
    return {
        "decades": [
            {"id": opt.id, "label": opt.label, "count": opt.count}
            for opt in year_index.available_decades()
        ],
        "unknown_count": year_index.unknown_count,
    }


@app.get("/user-books", response_model=UserBooksResponse)
def user_books(
    username: str = Query(..., min_length=1, max_length=MAX_USERNAME_LENGTH),
):
    normalized_input = username.strip().lstrip("@")
    if not normalized_input:
        raise HTTPException(status_code=400, detail="Username is required")
    if not USERNAME_PATTERN.fullmatch(normalized_input):
        raise HTTPException(status_code=422, detail="Username contains invalid characters")

    try:
        normalized, book_ids = fetch_user_books(normalized_input)
    except RuntimeError as exc:
        logger.warning("Failed to fetch Hardcover books for %s: %s", normalized_input, exc)
        raise HTTPException(
            status_code=502,
            detail="Unable to fetch books from Hardcover right now",
        ) from exc

    return {
        "username": normalized,
        "count": len(book_ids),
        "book_ids": book_ids,
    }
