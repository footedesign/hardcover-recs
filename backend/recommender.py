from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from .config import get_settings

import logging
import time

logger = logging.getLogger("uvicorn.error")


def _load_model() -> Tuple[np.ndarray, np.ndarray, Dict[int, int]]:
    """Load the trained factors once when the module is imported."""
    settings = get_settings()
    data = np.load(settings.model_path, allow_pickle=False)
    item_factors = np.ascontiguousarray(
        data["item_factors"].astype(np.float32)
    )
    index_to_book_id = data["index_to_book_id"].astype(np.int64)
    book_id_to_index = {
        int(book_id): idx for idx, book_id in enumerate(index_to_book_id)
    }
    logger.info(
        "Loaded SVD model: %d items, %d dims",
        item_factors.shape[0],
        item_factors.shape[1] if item_factors.ndim > 1 else 0,
    )
    return item_factors, index_to_book_id, book_id_to_index


ITEM_FACTORS, INDEX_TO_BOOK_ID, BOOK_ID_TO_INDEX = _load_model()


@dataclass
class Recommendation:
    book_id: int
    score: float


class SVDRecommender:
    """Thin wrapper around the pre-trained SVD latent factors."""

    def __init__(self):
        self.item_factors: np.ndarray = ITEM_FACTORS
        self.index_to_book_id: np.ndarray = INDEX_TO_BOOK_ID
        self.book_id_to_index = BOOK_ID_TO_INDEX

    def recommend(
        self,
        book_ids: Iterable[int],
        limit: int,
        offset: int = 0,
        exclude_book_ids: Optional[Iterable[int]] = None,
    ) -> tuple[List[Recommendation], int, dict]:
        input_indices = [
            self.book_id_to_index[bid]
            for bid in book_ids
            if bid in self.book_id_to_index
        ]

        if not input_indices:
            raise ValueError("None of the supplied book_ids exist in the model")

        timing: dict = {}

        pseudo_start = time.perf_counter()
        item_vecs = self.item_factors[input_indices]
        pseudo_user = item_vecs.mean(axis=0)
        timing["pseudo_ms"] = (time.perf_counter() - pseudo_start) * 1000

        score_start = time.perf_counter()
        scores = self.item_factors @ pseudo_user
        scores[input_indices] = -np.inf
        if exclude_book_ids:
            extra_indices = [
                self.book_id_to_index[bid]
                for bid in exclude_book_ids
                if bid in self.book_id_to_index
            ]
            if extra_indices:
                scores[extra_indices] = -np.inf

        total_candidates = np.sum(np.isfinite(scores))
        if total_candidates <= offset:
            timing["scoring_ms"] = (time.perf_counter() - score_start) * 1000
            return [], total_candidates, timing

        k = min(len(scores), max(offset + limit, 1))
        top_indices = np.argpartition(scores, -k)[-k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        sliced = top_indices[offset : offset + limit]
        timing["scoring_ms"] = (time.perf_counter() - score_start) * 1000

        recommendations = [
            Recommendation(
                book_id=int(self.index_to_book_id[idx]),
                score=float(scores[idx]),
            )
            for idx in sliced
            if np.isfinite(scores[idx])
        ]

        return recommendations, total_candidates, timing


recommender = SVDRecommender()
