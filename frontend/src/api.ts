import type {
  BookSummary,
  DecadeResponse,
  RecommendResponse,
  UserBooksResponse,
} from "./types";

const API_BASE_URL =
  window.__APP_CONFIG__?.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:8000";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(msg || "Request failed");
  }
  return (await res.json()) as T;
}

export async function searchBooks(
  query: string,
  limit = 8,
): Promise<BookSummary[]> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
  });
  const res = await fetch(`${API_BASE_URL}/search?${params.toString()}`);
  return handleResponse<BookSummary[]>(res);
}

export async function getRecommendations(
  bookIds: number[],
  limit = 10,
  offset = 0,
  genres: string[] = [],
  decades: string[] = [],
  excludeUnknownYears = false,
  excludeBookIds: number[] = [],
): Promise<RecommendResponse> {
  const res = await fetch(`${API_BASE_URL}/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      book_ids: bookIds,
      limit,
      offset,
      genres,
      decades,
      exclude_unknown_years: excludeUnknownYears,
      exclude_book_ids: excludeBookIds,
    }),
  });
  return handleResponse<RecommendResponse>(res);
}

export async function getGenres(limit = 50): Promise<string[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  const res = await fetch(`${API_BASE_URL}/genres?${params.toString()}`);
  return handleResponse<string[]>(res);
}

export async function getDecades(): Promise<DecadeResponse> {
  const res = await fetch(`${API_BASE_URL}/decades`);
  return handleResponse<DecadeResponse>(res);
}

export async function getUserBooks(
  username: string,
): Promise<UserBooksResponse> {
  const params = new URLSearchParams({ username });
  const res = await fetch(`${API_BASE_URL}/user-books?${params.toString()}`);
  return handleResponse<UserBooksResponse>(res);
}
