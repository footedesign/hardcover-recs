import sqlite3
from contextlib import contextmanager

from .config import get_settings


@contextmanager
def get_connection():
    settings = get_settings()
    db_uri = f"file:{settings.db_path}?mode=ro&immutable=1"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
