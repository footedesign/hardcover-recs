import sqlite3
from contextlib import contextmanager

from .config import get_settings


@contextmanager
def get_connection():
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
