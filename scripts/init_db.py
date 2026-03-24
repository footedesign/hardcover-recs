import sqlite3

from hardcover.runtime import DEFAULT_DB_PATH, ensure_parent_dir, env_path

DB_PATH = env_path("HARDCOVER_DB_PATH", DEFAULT_DB_PATH)

schema = """
PRAGMA journal_mode=WAL;

CREATE TABLE users (
  id INTEGER PRIMARY KEY
);

CREATE TABLE books (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  slug TEXT,
  description TEXT,
  cover_url TEXT,          -- from book.cached_image.url
  cover_color TEXT,        -- cached_image.color_name (optional)
  cover_w INTEGER,         -- cached_image.width
  cover_h INTEGER,         -- cached_image.height
  release_year INTEGER,    -- book.release_year
  pages INTEGER,           -- book.pages
  avg_rating REAL,         -- book.rating (average)
  users_count INTEGER,     -- book.users_count (people who shelved/read it)
  web_url TEXT             -- build from slug if Hardcover has canonical URLs
);

CREATE TABLE book_genres (
  book_id INTEGER NOT NULL,
  genre TEXT NOT NULL,
  tag_count INTEGER,
  PRIMARY KEY (book_id, genre),
  FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE book_authors (
  book_id INTEGER NOT NULL,
  author_id INTEGER,
  name TEXT NOT NULL,
  PRIMARY KEY (book_id, name),
  FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE ratings (
  user_id INTEGER NOT NULL,
  book_id INTEGER NOT NULL,
  rating REAL NOT NULL,
  PRIMARY KEY (user_id, book_id),
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE VIEW IF NOT EXISTS book_genre_agg AS
SELECT
  book_id,
  GROUP_CONCAT(genre, ', ') AS genres
FROM book_genres
GROUP BY book_id;

CREATE VIEW IF NOT EXISTS book_author_agg AS
SELECT
  book_id,
  GROUP_CONCAT(name, ', ') AS authors
FROM book_authors
GROUP BY book_id;

CREATE VIRTUAL TABLE IF NOT EXISTS book_search USING fts5(
  title,
  authors,
  genres,
  content=''
);
"""

def main():
    ensure_parent_dir(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(schema)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
