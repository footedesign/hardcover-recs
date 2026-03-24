from backend.recommender import recommender
from backend.services import fetch_book_details


def recommend_for_books(input_book_ids, top_n=20):
    recs, _, _ = recommender.recommend(input_book_ids, limit=top_n)
    return [rec.book_id for rec in recs]


if __name__ == "__main__":
    example_input = [1832979]  # adjust to your own IDs
    rec_ids = recommend_for_books(example_input, top_n=10)
    details = fetch_book_details(rec_ids)
    detail_map = {d["id"]: d for d in details}

    print("Recommendations:")
    for book_id in rec_ids:
        title = detail_map.get(book_id, {}).get("title", "(unknown title)")
        print(book_id, "-", title)
