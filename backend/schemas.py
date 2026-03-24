from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, conint


class BookSummary(BaseModel):
    id: int
    title: str
    authors: List[str] = Field(default_factory=list)
    cover_url: Optional[str] = None
    avg_rating: Optional[float] = None
    users_count: Optional[int] = None
    genres: List[str] = Field(default_factory=list)
    web_url: Optional[str] = None


class RecommendedBook(BookSummary):
    description: Optional[str] = None
    release_year: Optional[int] = None
    pages: Optional[int] = None
    score: Optional[float] = None


class RecommendRequest(BaseModel):
    book_ids: List[int] = Field(..., min_length=1, max_length=25)
    limit: conint(ge=1, le=50) = 10
    offset: conint(ge=0) = 0
    genres: List[str] = Field(default_factory=list, max_length=10)
    decades: List[str] = Field(default_factory=list, max_length=10)
    exclude_unknown_years: bool = False
    exclude_book_ids: List[int] = Field(default_factory=list, max_length=100)


class RecommendResponse(BaseModel):
    results: List[RecommendedBook]
    count: int
    next_offset: int


class UserBooksResponse(BaseModel):
    username: str
    count: int
    book_ids: List[int]
