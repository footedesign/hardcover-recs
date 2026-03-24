import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from hardcover.runtime import DEFAULT_DB_PATH, DEFAULT_MODEL_PATH, PROJECT_ROOT, env_path


def _parse_cors_origins(raw_value: str | None) -> tuple[str, ...]:
    if raw_value:
        origins = tuple(
            origin.strip().rstrip("/")
            for origin in raw_value.split(",")
            if origin.strip()
        )
        if origins:
            return origins
    return (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    )


@dataclass(frozen=True)
class Settings:
    """Centralized configuration for the API server."""

    project_root: Path
    db_path: Path
    model_path: Path
    cors_origins: tuple[str, ...]
    default_page_size: int
    max_page_size: int
    genre_cache_min_count: int
    decade_base_year: int

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            project_root=PROJECT_ROOT,
            db_path=env_path("HARDCOVER_DB_PATH", DEFAULT_DB_PATH).resolve(),
            model_path=env_path("HARDCOVER_MODEL_PATH", DEFAULT_MODEL_PATH).resolve(),
            cors_origins=_parse_cors_origins(os.getenv("HARDCOVER_CORS_ORIGINS")),
            default_page_size=10,
            max_page_size=50,
            genre_cache_min_count=int(os.getenv("HARDCOVER_GENRE_MIN_COUNT", "3")),
            decade_base_year=int(os.getenv("HARDCOVER_DECADE_BASE_YEAR", "1900")),
        )
        settings.validate_runtime_files()
        return settings

    def validate_runtime_files(self) -> None:
        if not self.db_path.is_file():
            raise RuntimeError(
                f"SQLite database not found at {self.db_path}. "
                "Set HARDCOVER_DB_PATH or create the database before starting the API."
            )
        if not self.model_path.is_file():
            raise RuntimeError(
                f"SVD model not found at {self.model_path}. "
                "Set HARDCOVER_MODEL_PATH or train the model before starting the API."
            )


@lru_cache(1)
def get_settings() -> Settings:
    return Settings.from_env()
