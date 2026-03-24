import sqlite3
from statistics import median

from hardcover.runtime import DEFAULT_DB_PATH, env_path

DB_PATH = env_path("HARDCOVER_DB_PATH", DEFAULT_DB_PATH)


def fetch_scalar(cursor, query: str):
    cursor.execute(query)
    result = cursor.fetchone()
    return result[0] if result else 0


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    total_users = fetch_scalar(cursor, "SELECT COUNT(*) FROM users")
    total_ratings = fetch_scalar(cursor, "SELECT COUNT(*) FROM ratings")
    total_books = fetch_scalar(cursor, "SELECT COUNT(DISTINCT book_id) FROM ratings")

    per_user_counts = [
        row[0] for row in cursor.execute("SELECT COUNT(*) FROM ratings GROUP BY user_id")
    ]
    average_ratings_per_user = (total_ratings / total_users) if total_users else 0
    median_ratings_per_user = median(per_user_counts) if per_user_counts else 0

    top_books = cursor.execute(
        """
        SELECT COALESCE(b.title, 'Unknown Title') AS title,
               r.book_id,
               COUNT(*) AS rating_count
        FROM ratings r
        LEFT JOIN books b ON b.id = r.book_id
        GROUP BY r.book_id
        ORDER BY rating_count DESC
        LIMIT 5
        """
    ).fetchall()

    oldest_books = cursor.execute(
        """
        SELECT title, release_year
        FROM books
        WHERE release_year IS NOT NULL
        ORDER BY release_year ASC, title ASC
        LIMIT 5
        """
    ).fetchall()

    highest_rated_books = cursor.execute(
        """
        SELECT
            COALESCE(b.title, 'Unknown Title') AS title,
            r.book_id,
            AVG(r.rating) AS avg_rating,
            COUNT(*) AS rating_count
        FROM ratings r
        LEFT JOIN books b ON b.id = r.book_id
        GROUP BY r.book_id
        HAVING rating_count > 0
        ORDER BY avg_rating DESC, rating_count DESC, title ASC
        LIMIT 5
        """
    ).fetchall()

    most_followed_books = cursor.execute(
        """
        SELECT title, users_count
        FROM books
        WHERE users_count IS NOT NULL
        ORDER BY users_count DESC, title ASC
        LIMIT 5
        """
    ).fetchall()

    longest_books = cursor.execute(
        """
        SELECT title, pages
        FROM books
        WHERE pages IS NOT NULL
        ORDER BY pages DESC, title ASC
        LIMIT 3
        """
    ).fetchall()

    longest_title_book = cursor.execute(
        """
        SELECT title, slug, LENGTH(title) AS title_length
        FROM books
        WHERE title IS NOT NULL
        ORDER BY title_length DESC, title ASC
        LIMIT 1
        """
    ).fetchone()

    shortest_title_book = cursor.execute(
        """
        SELECT title, slug, LENGTH(title) AS title_length
        FROM books
        WHERE title IS NOT NULL
        ORDER BY title_length ASC, title ASC
        LIMIT 1
        """
    ).fetchone()

    popular_genres = cursor.execute(
        """
        SELECT bg.genre, COUNT(*) AS rating_count
        FROM ratings r
        JOIN book_genres bg ON bg.book_id = r.book_id
        GROUP BY bg.genre
        ORDER BY rating_count DESC, bg.genre ASC
        LIMIT 5
        """
    ).fetchall()

    popular_authors = cursor.execute(
        """
        SELECT ba.name, COUNT(*) AS rating_count
        FROM ratings r
        JOIN book_authors ba ON ba.book_id = r.book_id
        GROUP BY ba.name
        ORDER BY rating_count DESC, ba.name ASC
        LIMIT 5
        """
    ).fetchall()

    print(f"Total users: {total_users:,}")
    print(f"Total unique books (by ratings): {total_books:,}")
    print(f"Total ratings: {total_ratings:,}")
    print(f"Average ratings per user: {average_ratings_per_user:.2f}")
    print(f"Median ratings per user: {median_ratings_per_user:.2f}")
    print("\nTop 25 most-rated books:")
    for idx, (title, book_id, rating_count) in enumerate(top_books, start=1):
        print(f"{idx:2}. {title} (Book ID {book_id}) — {rating_count} ratings")

    print("\n5 oldest books (by release year):")
    for title, release_year in oldest_books:
        print(f"- {title} — {release_year}")

    print("\n5 highest-rated books (avg rating + rating count):")
    for title, book_id, avg_rating_value, rating_count in highest_rated_books:
        print(f"- {title} (Book ID {book_id}) — {avg_rating_value:.2f} avg ({rating_count} ratings)")

    print("\nTop 5 books by users_count:")
    for title, count in most_followed_books:
        print(f"- {title} — {count} users")

    print("\nTop 3 longest books (pages):")
    for title, pages in longest_books:
        print(f"- {title} — {pages} pages")

    if longest_title_book:
        lt_title, lt_slug, lt_len = longest_title_book
        slug_text = lt_slug or "n/a"
        print(f"\nLongest title: {lt_title} (slug: {slug_text}) — {lt_len} characters")
    if shortest_title_book:
        st_title, st_slug, st_len = shortest_title_book
        slug_text = st_slug or "n/a"
        print(f"Shortest title: {st_title} (slug: {slug_text}) — {st_len} characters")

    print("\nTop 5 genres by rating volume:")
    if popular_genres:
        for genre, count in popular_genres:
            print(f"- {genre}: {count} ratings")
    else:
        print("- No genre data available. Re-run the fetch after the genre migration.")

    print("\nTop 5 authors by ratings:")
    if popular_authors:
        for author, count in popular_authors:
            print(f"- {author}: {count} ratings")
    else:
        print("- No author data available. Re-run the fetch after the author migration.")

    conn.close()


if __name__ == "__main__":
    main()
