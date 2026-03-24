from __future__ import annotations

from typing import Dict, List, Optional, Set

from .config import get_settings
from .database import get_connection


class GenreIndex:
    def __init__(self):
        self.settings = get_settings()
        self.book_to_genres: Dict[int, Set[str]] = {}
        self.genre_to_books: Dict[str, Set[int]] = {}
        self.genre_counts: Dict[str, int] = {}
        self._load()

    def _load(self):
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT book_id, genre, tag_count
                FROM book_genres
                WHERE tag_count >= ?
                """,
            (self.settings.genre_cache_min_count,),
        ).fetchall()
        book_map: Dict[int, Set[str]] = {}
        genre_to_books: Dict[str, Set[int]] = {}
        genre_counts: Dict[str, int] = {}
        for row in rows:
            book_id = int(row["book_id"])
            genre = (row["genre"] or "").strip()
            if not genre:
                continue
            lower_genre = genre.lower()
            book_map.setdefault(book_id, set()).add(lower_genre)
            genre_to_books.setdefault(lower_genre, set()).add(book_id)
            genre_counts[lower_genre] = genre_counts.get(lower_genre, 0) + row[
                "tag_count"
            ]
        self.book_to_genres = book_map
        self.genre_to_books = genre_to_books
        self.genre_counts = genre_counts

    def matches(self, book_id: int, required_genres: Set[str]) -> bool:
        if not required_genres:
            return True
        genres = self.book_to_genres.get(book_id)
        if not genres:
            return False
        return required_genres.issubset(genres)

    def candidate_ids(self, required_genres: Set[str]) -> Optional[Set[int]]:
        if not required_genres:
            return None
        sets: List[Set[int]] = []
        for genre in required_genres:
            books = self.genre_to_books.get(genre)
            if not books:
                return set()
            sets.append(books)
        # Start with smallest set to minimize intersections
        smallest = min(sets, key=len)
        candidates = set(smallest)
        for s in sets:
            if s is smallest:
                continue
            candidates.intersection_update(s)
            if not candidates:
                break
        return candidates


genre_index = GenreIndex()
