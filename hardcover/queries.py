# hardcover/queries.py
USER_RATINGS_QUERY = """
query UserRatings($limit: Int!, $offset: Int!) {
  users(limit: $limit, offset: $offset) {
    id
    user_books(
      where: { rating: { _is_null: false } }
      limit: 5000
    ) {
      rating
      book_id
      book {
        title
        contributions {
          author {
            id
            name
          }
        }
        slug
        pages
        release_year
        rating
        users_count
        cached_image
        description
        cached_tags(path: "Genre")
      }
    }
  }
}
"""

USER_BOOKS_BY_USERNAME_QUERY = """
query UserBooks($username: citext!) {
  user_books(where: {user: {username: {_eq: $username}}}) {
    book {
      id
    }
  }
}
"""
