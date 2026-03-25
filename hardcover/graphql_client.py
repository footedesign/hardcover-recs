import os
import time

import requests

from .config import GRAPHQL_URL, API_KEY

REQUEST_TIMEOUT_SECONDS = int(os.getenv("HARDCOVER_REQUEST_TIMEOUT_SECONDS", "30"))
MAX_RETRIES = int(os.getenv("HARDCOVER_REQUEST_MAX_RETRIES", "5"))
INITIAL_BACKOFF_SECONDS = float(os.getenv("HARDCOVER_REQUEST_INITIAL_BACKOFF_SECONDS", "5"))
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def gql(query: str, variables: dict | None = None) -> dict:
    headers = {
        "Content-Type": "application/json",
    }
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    backoff_seconds = INITIAL_BACKOFF_SECONDS
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                GRAPHQL_URL,
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            break
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code not in RETRYABLE_STATUS_CODES or attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"Hardcover API request failed with status {status_code}"
                ) from exc
            print(
                (
                    f"hardcover: request failed with status {status_code}; "
                    f"retrying in {backoff_seconds:.1f}s "
                    f"(attempt {attempt}/{MAX_RETRIES})"
                ),
                flush=True,
            )
            last_error = exc
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError("Hardcover API request failed") from exc
            print(
                (
                    "hardcover: request failed with a network error; "
                    f"retrying in {backoff_seconds:.1f}s "
                    f"(attempt {attempt}/{MAX_RETRIES})"
                ),
                flush=True,
            )
            last_error = exc

        time.sleep(backoff_seconds)
        backoff_seconds *= 2
    else:
        raise RuntimeError("Hardcover API request failed") from last_error

    try:
        data = resp.json()
    except ValueError as exc:
        raise RuntimeError("Hardcover API returned invalid JSON") from exc

    if "errors" in data:
        raise RuntimeError("Hardcover API returned a GraphQL error")
    return data["data"]
