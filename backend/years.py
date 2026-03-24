from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .config import get_settings
from .database import get_connection


@dataclass
class DecadeOption:
    id: str
    label: str
    start_year: Optional[int]
    end_year: Optional[int]
    count: int


class YearIndex:
    def __init__(self):
        self.settings = get_settings()
        self.book_year: Dict[int, Optional[int]] = {}
        self.decade_ranges: Dict[str, Tuple[int, int]] = {}
        self.decade_options: List[DecadeOption] = []
        self.unknown_count = 0
        self.bucket_members: Dict[str, Set[int]] = {}
        self.unknown_ids: Set[int] = set()
        self._load()

    def _load(self):
        base_year = self.settings.decade_base_year
        with get_connection() as conn:
            rows = conn.execute("SELECT id, release_year FROM books").fetchall()

        non_null_years: List[int] = []
        unknown_count = 0
        for row in rows:
            book_id = int(row["id"])
            year = row["release_year"]
            if year is None or year <= 0 or year > 2025:
                self.book_year[book_id] = None
                unknown_count += 1
                self.unknown_ids.add(book_id)
            else:
                int_year = int(year)
                self.book_year[book_id] = int_year
                non_null_years.append(int_year)
        self.unknown_count = unknown_count

        if non_null_years:
            inferred_max = max(non_null_years)
        else:
            inferred_max = base_year
        max_year = min(inferred_max, 2025)

        bucket_counts: Dict[str, int] = {}
        bucket_ranges: Dict[str, Tuple[int, int]] = {}
        bucket_labels: Dict[str, str] = {}

        # Before base year bucket
        before_id = f"before-{base_year}"
        bucket_counts[before_id] = 0
        bucket_ranges[before_id] = (float("-inf"), base_year - 1)
        bucket_labels[before_id] = f"Before {base_year}"

        # Decades up to present
        decade_start = base_year
        while decade_start <= (max_year // 10) * 10:
            decade_id = f"{decade_start}s"
            bucket_counts[decade_id] = 0
            bucket_ranges[decade_id] = (decade_start, decade_start + 9)
            bucket_labels[decade_id] = f"{decade_start}s"
            decade_start += 10

        bucket_members: Dict[str, Set[int]] = {before_id: set()}

        for book_id, year in self.book_year.items():
            if year is None:
                continue
            if year < base_year:
                bucket_counts[before_id] += 1
                bucket_members.setdefault(before_id, set()).add(book_id)
            else:
                decade = (year // 10) * 10
                decade_id = f"{decade}s"
                if decade_id not in bucket_counts:
                    bucket_counts[decade_id] = 0
                    bucket_ranges[decade_id] = (decade, decade + 9)
                    bucket_labels[decade_id] = f"{decade}s"
                bucket_counts[decade_id] += 1
                bucket_members.setdefault(decade_id, set()).add(book_id)

        options: List[DecadeOption] = []
        if bucket_counts[before_id]:
            options.append(
                DecadeOption(
                    id=before_id,
                    label=bucket_labels[before_id],
                    start_year=None,
                    end_year=base_year - 1,
                    count=bucket_counts[before_id],
                )
            )

        for decade_id in sorted(
            (key for key in bucket_counts.keys() if key.endswith("s")),
            key=lambda k: int(k[:-1]),
        ):
            options.append(
                DecadeOption(
                    id=decade_id,
                    label=bucket_labels[decade_id],
                    start_year=bucket_ranges[decade_id][0],
                    end_year=bucket_ranges[decade_id][1],
                    count=bucket_counts[decade_id],
                )
            )

        self.decade_ranges = bucket_ranges
        self.decade_options = options
        self.bucket_members = bucket_members

    def matches(
        self,
        book_id: int,
        decades: Set[str],
        exclude_unknown: bool,
    ) -> bool:
        year = self.book_year.get(book_id)
        if year is None:
            if decades:
                return False
            return not exclude_unknown

        if not decades:
            return True

        for decade_id in decades:
            rng = self.decade_ranges.get(decade_id)
            if not rng:
                continue
            start, end = rng
            if start == float("-inf"):
                if year <= end:
                    return True
            elif start <= year <= end:
                return True
        return False

    def available_decades(self) -> List[DecadeOption]:
        return self.decade_options

    def candidate_ids(
        self,
        decades: Set[str],
        exclude_unknown: bool,
    ) -> Optional[Set[int]]:
        if not decades and not exclude_unknown:
            return None

        candidates: Optional[Set[int]] = None
        if decades:
            union: Set[int] = set()
            for decade_id in decades:
                books = self.bucket_members.get(decade_id)
                if books:
                    union.update(books)
            candidates = union
        if exclude_unknown:
            if candidates is None:
                if self.unknown_count == len(self.book_year):
                    return set()
                return None
            candidates = {bid for bid in candidates if self.book_year.get(bid)}

        return candidates


year_index = YearIndex()
