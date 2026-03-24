export type BookSummary = {
  id: number;
  title: string;
  authors: string[];
  cover_url?: string | null;
  avg_rating?: number | null;
  users_count?: number | null;
  genres: string[];
  web_url?: string | null;
};

export type Recommendation = BookSummary & {
  description?: string | null;
  release_year?: number | null;
  pages?: number | null;
  score?: number | null;
};

export type RecommendResponse = {
  results: Recommendation[];
  count: number;
  next_offset: number;
};

export type DecadeOption = {
  id: string;
  label: string;
  count: number;
};

export type DecadeResponse = {
  decades: DecadeOption[];
  unknown_count: number;
};

export type UserBooksResponse = {
  username: string;
  count: number;
  book_ids: number[];
};
