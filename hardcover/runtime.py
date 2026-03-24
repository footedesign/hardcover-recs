from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = Path("/data/hardcover.db")
DEFAULT_MODEL_PATH = Path("/data/svd_model.npz")


def env_path(name: str, default: Path) -> Path:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    return Path(raw_value).expanduser()


def ensure_parent_dir(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
