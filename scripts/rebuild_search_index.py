import sqlite3

from hardcover.runtime import DEFAULT_DB_PATH, env_path

DB_PATH = env_path("HARDCOVER_DB_PATH", DEFAULT_DB_PATH)


def rebuild_search_index():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("INSERT INTO book_search(book_search) VALUES('delete-all')")
    cur.execute(
        """
        INSERT INTO book_search (rowid, title, authors, genres)
        WITH filtered_genres AS (
            SELECT book_id, GROUP_CONCAT(genre, ', ') AS genres
            FROM book_genres
            WHERE tag_count > 2
            GROUP BY book_id
        )
        SELECT
            b.id,
            COALESCE(b.title, ''),
            COALESCE(aa.authors, ''),
            COALESCE(fg.genres, '')
        FROM books b
        LEFT JOIN book_author_agg aa ON aa.book_id = b.id
        LEFT JOIN filtered_genres fg ON fg.book_id = b.id
        WHERE b.title IS NOT NULL
        """
    )
    conn.commit()
    conn.close()


def main():
    rebuild_search_index()
    print("book_search index rebuilt.")


if __name__ == "__main__":
    main()
