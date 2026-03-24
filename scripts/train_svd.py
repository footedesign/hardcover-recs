import sqlite3

import numpy as np
import scipy.sparse as sp
from sklearn.decomposition import TruncatedSVD

from hardcover.runtime import DEFAULT_DB_PATH, DEFAULT_MODEL_PATH, ensure_parent_dir, env_path

DB_PATH = env_path("HARDCOVER_DB_PATH", DEFAULT_DB_PATH)
MODEL_PATH = env_path("HARDCOVER_MODEL_PATH", DEFAULT_MODEL_PATH)


def load_ratings():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id, book_id, rating FROM ratings")
    rows = cur.fetchall()
    conn.close()
    return rows


def build_mappings(rows):
    user_ids = sorted({r[0] for r in rows})
    book_ids = sorted({r[1] for r in rows})

    user_id_to_index = {uid: i for i, uid in enumerate(user_ids)}
    index_to_user_id = np.array(user_ids, dtype=np.int64)

    book_id_to_index = {bid: i for i, bid in enumerate(book_ids)}
    index_to_book_id = np.array(book_ids, dtype=np.int64)

    return user_id_to_index, index_to_user_id, book_id_to_index, index_to_book_id


def build_sparse_matrix(rows, user_id_to_index, book_id_to_index):
    user_indices = []
    book_indices = []
    ratings = []

    for user_id, book_id, rating in rows:
        user_indices.append(user_id_to_index[user_id])
        book_indices.append(book_id_to_index[book_id])
        ratings.append(float(rating))

    user_indices = np.array(user_indices, dtype=np.int32)
    book_indices = np.array(book_indices, dtype=np.int32)
    ratings = np.array(ratings, dtype=np.float32)

    num_users = len(user_id_to_index)
    num_items = len(book_id_to_index)

    # users x items
    mat = sp.coo_matrix(
        (ratings, (user_indices, book_indices)),
        shape=(num_users, num_items),
    )
    return mat.tocsr()


def main():
    rows = load_ratings()
    print(f"Loaded {len(rows)} ratings")

    mappings = build_mappings(rows)
    (
        user_id_to_index,
        index_to_user_id,
        book_id_to_index,
        index_to_book_id,
    ) = mappings

    mat = build_sparse_matrix(rows, user_id_to_index, book_id_to_index)

    # You can tune n_components based on how big the matrix is.
    n_components = 64
    print(f"Fitting TruncatedSVD with {n_components} components...")

    svd = TruncatedSVD(
        n_components=n_components,
        n_iter=10,
        random_state=42,
    )
    # mat: users x items
    svd.fit(mat)

    # Item (book) embeddings: project identity basis in item space
    # A simpler way: transform the transpose
    item_latent = svd.components_.T  # shape: (num_items, n_components)

    ensure_parent_dir(MODEL_PATH)
    np.savez(
        MODEL_PATH,
        item_factors=item_latent,
        index_to_book_id=index_to_book_id,
    )
    print("Model saved to", MODEL_PATH)


if __name__ == "__main__":
    main()
