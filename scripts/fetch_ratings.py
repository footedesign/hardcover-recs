# scripts/fetch_ratings.py
import json
import sqlite3
import sys
import time

from tqdm import tqdm

from hardcover.runtime import DEFAULT_DB_PATH, PROJECT_ROOT, ensure_parent_dir, env_path

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hardcover.graphql_client import gql
from hardcover.queries import USER_RATINGS_QUERY

DB_PATH = env_path("HARDCOVER_DB_PATH", DEFAULT_DB_PATH)

BATCH_SIZE = 100           # API limits
RATE_LIMIT_SECONDS = 5     # Time to wait between requests to respect rate limits

def extract_genres(raw_tags):
    """Normalize Hardcover cached_tags payloads into structured genre objects."""
    def maybe_json_load(value: str):
        text = value.strip()
        if not text:
            return None
        if (text.startswith("{") and text.endswith("}")) or (
            text.startswith("[") and text.endswith("]")
        ):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return None
        return None

    collected = []

    def collect(entry):
        if not isinstance(entry, dict):
            return
        if "tag" in entry:
            tag_name = (entry.get("tag") or "").strip()
            if tag_name:
                collected.append(
                    {
                        "genre": tag_name,
                        "tag_count": entry.get("count"),
                    }
                )

    def walk(value):
        if value is None:
            return
        if isinstance(value, str):
            parsed = maybe_json_load(value)
            if parsed is not None:
                walk(parsed)
            else:
                # raw string (single genre)
                collect({"tag": value})
        elif isinstance(value, dict):
            collect(value)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                walk(item)

    walk(raw_tags)

    deduped = []
    seen = set()
    for entry in collected:
        key = entry["genre"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def extract_authors(contributions):
    """Normalize Hardcover contributions into structured author entries."""
    authors = []
    if not contributions:
        return []

    for entry in contributions:
        if not isinstance(entry, dict):
            continue
        author = entry.get("author")
        if not isinstance(author, dict):
            continue
        name = (author.get("name") or "").strip()
        if not name:
            continue
        author_id = author.get("id")
        try:
            author_id = int(author_id) if author_id is not None else None
        except (TypeError, ValueError):
            author_id = None
        authors.append({"author_id": author_id, "name": name})

    deduped = []
    seen = set()
    for author in authors:
        key = (author["author_id"], author["name"].lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(author)
    return deduped


def upsert_data(conn, users):
    cur = conn.cursor()
    for user in users:
        uid = int(user["id"])

        user_books = user.get("user_books") or []
        # Skip users with no rated books
        if not user_books:
            continue

        cur.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (uid,))

        for ub in user_books:
            rating = ub["rating"]
            book_id = int(ub["book_id"])
            book_data = ub.get("book") or {}
            title = book_data.get("title")
            slug = book_data.get("slug")
            description = book_data.get("description")
            pages = book_data.get("pages")
            release_year = book_data.get("release_year")
            avg_rating = book_data.get("rating")
            users_count = book_data.get("users_count")
            cached_image = book_data.get("cached_image") or {}
            cover_url = cached_image.get("url")
            cover_color = cached_image.get("color_name")
            cover_w = cached_image.get("width")
            cover_h = cached_image.get("height")
            genre_records = extract_genres(book_data.get("cached_tags"))
            author_records = extract_authors(book_data.get("contributions"))
            web_url = f"https://hardcover.app/books/{slug}" if slug else None

            if rating is None:
                continue

            if title:
                cur.execute(
                    """
                    INSERT INTO books (
                        id, title, slug, description, cover_url, cover_color,
                        cover_w, cover_h, release_year, pages, avg_rating,
                        users_count, web_url
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title=excluded.title,
                        slug=excluded.slug,
                        description=excluded.description,
                        cover_url=excluded.cover_url,
                        cover_color=excluded.cover_color,
                        cover_w=excluded.cover_w,
                        cover_h=excluded.cover_h,
                        release_year=excluded.release_year,
                        pages=excluded.pages,
                        avg_rating=excluded.avg_rating,
                        users_count=excluded.users_count,
                        web_url=excluded.web_url
                    """,
                    (
                        book_id,
                        title,
                        slug,
                        description,
                        cover_url,
                        cover_color,
                        cover_w,
                        cover_h,
                        release_year,
                        pages,
                        avg_rating,
                        users_count,
                        web_url,
                    ),
                )

                if genre_records:
                    cur.executemany(
                        """
                        INSERT INTO book_genres (
                            book_id, genre, tag_count
                        )
                        VALUES (?, ?, ?)
                        ON CONFLICT(book_id, genre) DO UPDATE SET
                            tag_count=excluded.tag_count
                        """,
                        [
                            (
                                book_id,
                                record["genre"],
                                record.get("tag_count"),
                            )
                            for record in genre_records
                        ],
                    )

                if author_records:
                    cur.executemany(
                        """
                        INSERT INTO book_authors (
                            book_id, author_id, name
                        )
                        VALUES (?, ?, ?)
                        ON CONFLICT(book_id, name) DO UPDATE SET
                            author_id=COALESCE(excluded.author_id, author_id)
                        """,
                        [
                            (
                                book_id,
                                record.get("author_id"),
                                record["name"],
                            )
                            for record in author_records
                        ],
                    )

            cur.execute(
                "INSERT OR REPLACE INTO ratings (user_id, book_id, rating) VALUES (?, ?, ?)",
                (uid, book_id, float(rating)),
            )

    conn.commit()

def main():
    ensure_parent_dir(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    offset = 0

    with tqdm(unit="users") as progress:
        while True:
            cycle_start = time.monotonic()
            variables = {
                "limit": BATCH_SIZE,
                "offset": offset,
            }
            data = gql(USER_RATINGS_QUERY, variables)
            users = data["users"]
            if not users:
                break

            upsert_data(conn, users)
            progress.update(len(users))
            offset += BATCH_SIZE

            sleep_for = RATE_LIMIT_SECONDS - (time.monotonic() - cycle_start)
            if sleep_for > 0:
                time.sleep(sleep_for)

    conn.close()


if __name__ == "__main__":
    main()
