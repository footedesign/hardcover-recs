import { useEffect, useMemo, useRef, useState } from "react";
import {
  getDecades,
  getGenres,
  getRecommendations,
  getUserBooks,
  searchBooks,
} from "./api";
import type { BookSummary, DecadeOption, Recommendation } from "./types";

const PAGE_SIZE = 10;

function App() {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<BookSummary[]>([]);
  const [selectedBooks, setSelectedBooks] = useState<BookSummary[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [offset, setOffset] = useState(0);
  const [totalMatches, setTotalMatches] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingRecs, setIsLoadingRecs] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableGenres, setAvailableGenres] = useState<string[]>([]);
  const [selectedGenres, setSelectedGenres] = useState<string[]>([]);
  const [availableDecades, setAvailableDecades] = useState<DecadeOption[]>([]);
  const [selectedDecades, setSelectedDecades] = useState<string[]>([]);
  const [excludeUnknownYears, setExcludeUnknownYears] = useState(false);
  const [hasRequestedRecs, setHasRequestedRecs] = useState(false);
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const filtersContainerRef = useRef<HTMLDivElement | null>(null);
  const [bookshelfInput, setBookshelfInput] = useState("");
  const [isFetchingBookshelf, setIsFetchingBookshelf] = useState(false);
  const [bookshelfBookIds, setBookshelfBookIds] = useState<number[]>([]);
  const [bookshelfCount, setBookshelfCount] = useState(0);
  const [bookshelfUsername, setBookshelfUsername] = useState<string | null>(null);
  const [bookshelfStatus, setBookshelfStatus] = useState(
    "Enter your Hardcover username to exclude your own books.",
  );

  useEffect(() => {
    if (!query.trim()) {
      setSuggestions([]);
      return;
    }

    const handle = setTimeout(async () => {
      setIsSearching(true);
      try {
        const matches = await searchBooks(query, 8);
        setSuggestions(matches);
      } catch (err) {
        console.error(err);
      } finally {
        setIsSearching(false);
      }
    }, 250);

    return () => clearTimeout(handle);
  }, [query]);

  useEffect(() => {
    if (!isFilterOpen) {
      return;
    }

    const handleClick = (event: MouseEvent) => {
      if (
        filtersContainerRef.current &&
        !filtersContainerRef.current.contains(event.target as Node)
      ) {
        setIsFilterOpen(false);
      }
    };

    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsFilterOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);

    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [isFilterOpen]);

  const selectedIds = useMemo(
    () => new Set(selectedBooks.map((book) => book.id)),
    [selectedBooks],
  );

  useEffect(() => {
    setRecommendations([]);
    setOffset(0);
    setTotalMatches(0);
    setHasRequestedRecs(false);
  }, [
    selectedBooks,
    selectedGenres,
    selectedDecades,
    excludeUnknownYears,
    bookshelfBookIds,
  ]);

  useEffect(() => {
    (async () => {
      try {
        const genres = await getGenres();
        setAvailableGenres(genres);
        const decadeResp = await getDecades();
        setAvailableDecades(decadeResp.decades);
      } catch (err) {
        console.error(err);
      }
    })();
  }, []);

  const handleSelect = (book: BookSummary) => {
    if (selectedIds.has(book.id)) {
      return;
    }
    setSelectedBooks((prev) => [...prev, book]);
    setQuery("");
    setSuggestions([]);
  };

  const removeSelected = (id: number) => {
    setSelectedBooks((prev) => prev.filter((book) => book.id !== id));
  };

  const fetchRecommendations = async (reset: boolean) => {
    if (!selectedBooks.length) {
      return;
    }
    if (reset) {
      setHasRequestedRecs(true);
    }
    setIsLoadingRecs(true);
    setError(null);
    try {
      const pageOffset = reset ? 0 : offset;
      const res = await getRecommendations(
        selectedBooks.map((book) => book.id),
        PAGE_SIZE,
        pageOffset,
        selectedGenres,
        selectedDecades,
        excludeUnknownYears,
        bookshelfBookIds,
      );
      setTotalMatches(res.count);
      setOffset(res.next_offset);
      setRecommendations((prev) =>
        reset ? res.results : [...prev, ...res.results],
      );
    } catch (err) {
      console.error(err);
      setError(
        err instanceof Error ? err.message : "Unable to fetch recommendations.",
      );
    } finally {
      setIsLoadingRecs(false);
    }
  };

  const handleRecommend = () => fetchRecommendations(true);
  const loadMore = () => fetchRecommendations(false);
  const toggleGenre = (genre: string) => {
    setSelectedGenres((prev) =>
      prev.includes(genre)
        ? prev.filter((item) => item !== genre)
        : [...prev, genre],
    );
  };
  const clearGenres = () => setSelectedGenres([]);
  const toggleDecade = (decade: string) => {
    setSelectedDecades((prev) =>
      prev.includes(decade)
        ? prev.filter((item) => item !== decade)
        : [...prev, decade],
    );
  };
  const clearDecades = () => setSelectedDecades([]);
  const toggleExcludeUnknown = () =>
    setExcludeUnknownYears((prev) => !prev);
  const clearSelectedBooks = () => setSelectedBooks([]);
  const handleFetchBookshelf = async () => {
    const raw = bookshelfInput.trim();
    const stripped = raw.replace(/^@+/, "");
    if (!stripped) {
      setBookshelfBookIds([]);
      setBookshelfCount(0);
      setBookshelfUsername(null);
      setBookshelfStatus("Enter a username to fetch your bookshelf.");
      return;
    }
    setIsFetchingBookshelf(true);
    try {
      const data = await getUserBooks(stripped);
      setBookshelfBookIds(data.book_ids);
      setBookshelfCount(data.count);
      setBookshelfUsername(`@${data.username}`);
      if (data.count === 0) {
        setBookshelfStatus("0 books returned — your profile may be private.");
      } else {
        setBookshelfStatus(
          `Excluding ${data.count.toLocaleString()} books from @${data.username}`,
        );
      }
    } catch (err) {
      setBookshelfBookIds([]);
      setBookshelfCount(0);
      setBookshelfUsername(null);
      setBookshelfStatus(
        err instanceof Error ? err.message : "Unable to fetch bookshelf.",
      );
    } finally {
      setIsFetchingBookshelf(false);
    }
  };

  const clearBookshelf = () => {
    setBookshelfBookIds([]);
    setBookshelfCount(0);
    setBookshelfUsername(null);
    setBookshelfInput("");
    setBookshelfStatus("Enter your Hardcover username to exclude your own books.");
  };

  const filtersAppliedCount =
    selectedGenres.length +
    selectedDecades.length +
    (excludeUnknownYears ? 1 : 0) +
    (bookshelfBookIds.length > 0 ? 1 : 0);
  const hasMore = recommendations.length < totalMatches;
  const showEmptyState =
    hasRequestedRecs && !isLoadingRecs && !error && recommendations.length === 0;
  const showPrompt =
    !hasRequestedRecs && selectedBooks.length > 0 && !isLoadingRecs && !error;

  return (
    <div className="app-shell">
      <header>
        <h1>Book Recommendations</h1>
        <p>
          Search for books you love and let the recommender surface similar
          titles based on public Hardcover reader ratings.
        </p>
      </header>

      <section className="search-section">
        <form
          className="search-action-row"
          onSubmit={(e) => {
            e.preventDefault();
            handleRecommend();
          }}
        >
          <input
            className="search-input"
            type="text"
            placeholder="Search for a book title…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="filters-control" ref={filtersContainerRef}>
            <button
              type="button"
              className={`filters-toggle${
                filtersAppliedCount ? " active" : ""
              }`}
              onClick={() => setIsFilterOpen((open) => !open)}
              aria-haspopup="dialog"
              aria-expanded={isFilterOpen}
            >
              Filters
              {filtersAppliedCount > 0 ? ` (${filtersAppliedCount})` : ""}
              &nbsp;
              <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" viewBox="0 0 16 16">
                <path d="M1.5 1.5A.5.5 0 0 1 2 1h12a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-.128.334L10 8.692V13.5a.5.5 0 0 1-.342.474l-3 1A.5.5 0 0 1 6 14.5V8.692L1.628 3.834A.5.5 0 0 1 1.5 3.5zm1 .5v1.308l4.372 4.858A.5.5 0 0 1 7 8.5v5.306l2-.666V8.5a.5.5 0 0 1 .128-.334L13.5 3.308V2z"/>
              </svg>
            </button>
            {isFilterOpen && (
              <div className="filters-popover" role="dialog" aria-label="Filters">
                <div className="bookshelf-filter">
                  <p>Exclude books from your bookshelf in the recommendation results.</p>
                  <div className="bookshelf-input-row">
                    <div className="username-input">
                      <span>@</span>
                      <input
                        type="text"
                        placeholder="username"
                        value={bookshelfInput}
                        onChange={(e) =>
                          setBookshelfInput(e.target.value.replace(/^@+/, ""))
                        }
                      />
                    </div>
                    <button
                      type="button"
                      className="mini-button"
                      onClick={handleFetchBookshelf}
                      disabled={isFetchingBookshelf}
                    >
                      {isFetchingBookshelf ? "Loading…" : "Get my books"}
                    </button>
                  </div>
                  <small className="bookshelf-status">
                    {isFetchingBookshelf ? "Fetching books…" : bookshelfStatus}
                    {bookshelfBookIds.length > 0 && (
                      <button
                        type="button"
                        className="link-button"
                        onClick={clearBookshelf}
                      >
                        Clear
                      </button>
                    )}
                  </small>
                </div>
                <div className="filter-section">
                  <div className="filter-header">
                    <h3>Genres</h3>
                    {selectedGenres.length > 0 && (
                      <button
                        type="button"
                        className="link-button"
                        onClick={clearGenres}
                      >
                        Clear
                      </button>
                    )}
                  </div>
                  <p className="filter-hint">
                    Recommendations will be filtered by the selected genre(s).
                  </p>
                  <div className="genre-filter">
                    {availableGenres.length === 0 && (
                      <span className="filter-hint">Loading genres…</span>
                    )}
                    {availableGenres.map((genre) => {
                      const active = selectedGenres.includes(genre);
                      return (
                        <button
                          type="button"
                          key={genre}
                          className={`filter-chip${active ? " selected" : ""}`}
                          onClick={() => toggleGenre(genre)}
                        >
                          {genre}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="filter-section">
                  <div className="filter-header">
                    <h3>Decades</h3>
                    {selectedDecades.length > 0 && (
                      <button
                        type="button"
                        className="link-button"
                        onClick={clearDecades}
                      >
                        Clear
                      </button>
                    )}
                  </div>
                  <p className="filter-hint">
                    Combine decade filters with genres to zero in on specific eras.
                  </p>
                  <div className="genre-filter">
                    {availableDecades.length === 0 && (
                      <span className="filter-hint">Loading decades…</span>
                    )}
                    {availableDecades.map((decade) => {
                      const active = selectedDecades.includes(decade.id);
                      return (
                        <button
                          type="button"
                          key={decade.id}
                          className={`filter-chip${active ? " selected" : ""}`}
                          onClick={() => toggleDecade(decade.id)}
                        >
                          {decade.label}
                        </button>
                      );
                    })}
                    <button
                      type="button"
                      className={`filter-chip${
                        excludeUnknownYears ? " selected" : ""
                      }`}
                      onClick={toggleExcludeUnknown}
                    >
                      Exclude unknown year
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
          <button
            type="submit"
            className="cta"
            disabled={!selectedBooks.length || isLoadingRecs}
          >
            {isLoadingRecs ? "Finding matches…" : "Get recommendations"}
          </button>
        </form>
        {query && (
          <small>{isSearching ? "Searching…" : "Pick a book from the list"}</small>
        )}
        {suggestions.length > 0 && (
          <ul className="suggestions">
            {suggestions.map((book) => (
              <li key={book.id} onClick={() => handleSelect(book)}>
                <strong>{book.title}</strong>
                {book.authors.length > 0 && (
                  <span> · {book.authors.join(", ")}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="selected-section">
        <div className="filter-header">
          <h2>Selected books</h2>
          {selectedBooks.length > 0 && (
            <button
              type="button"
              className="link-button"
              onClick={clearSelectedBooks}
            >
              Clear
            </button>
          )}
        </div>
        {selectedBooks.length === 0 ? (
          <p className="empty-state">
            Add at least one book to unlock personalized recommendations.
          </p>
        ) : (
          <>
            <div className="selected-books">
              {selectedBooks.map((book) => (
                <span className="pill" key={book.id}>
                  {book.title}
                  <button onClick={() => removeSelected(book.id)} aria-label="Remove">
                    ×
                  </button>
                </span>
              ))}
            </div>
          </>
        )}
      </section>

      <section className="results-section">
        <h2>Recommendations</h2>
        {error && <p className="empty-state">{error}</p>}
        {showPrompt && (
          <p className="empty-state">Press “Get recommendations” to see matches.</p>
        )}
        {isLoadingRecs && (
          <p className="loading-state">Fetching recommendations…</p>
        )}
        {showEmptyState && (
          <p className="empty-state">No matches yet. Try different books or filters.</p>
        )}

        <div className="recommendations">
          {recommendations.map((rec) => (
            <article className="rec-card" key={rec.id}>
              {rec.cover_url ? (
                <img src={rec.cover_url} alt={rec.title} />
              ) : (
                <div style={{ width: 96, height: 144, background: "#e2e8f0" }} />
              )}
              <div>
                <h3>
                  <a href={rec.web_url ?? "#"} target="_blank" rel="noreferrer">
                    {rec.title}
                  </a>
                </h3>
                {rec.authors.length > 0 && (
                  <div className="rec-meta">
                    <span>{rec.authors.join(", ")}</span>
                  </div>
                )}
                <div className="rec-meta">
                  {rec.avg_rating && (
                    <span>⭐ {rec.avg_rating.toFixed(2)} avg</span>
                  )}
                  {rec.avg_rating && <span>&bull;</span>}
                  {rec.users_count && (
                    <span>{rec.users_count.toLocaleString()} readers</span>
                  )}
                  {rec.users_count && <span>&bull;</span>}
                  {rec.release_year && <span>{rec.release_year}</span>}
                  {rec.release_year && <span>&bull;</span>}
                  {rec.pages && <span>{rec.pages} pages</span>}
                </div>
                <p>
                  {rec.description ??
                    "No description available for this title yet."}
                </p>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  {rec.genres.map((genre) => (
                    <span className="genre-chip" key={`${rec.id}-${genre}`}>
                      {genre}
                    </span>
                  ))}
                </div>
              </div>
            </article>
          ))}
        </div>

        {hasMore && !isLoadingRecs && (
          <button className="load-more" onClick={loadMore}>
            Load 10 more
          </button>
        )}
      </section>
    </div>
  );
}

export default App;
