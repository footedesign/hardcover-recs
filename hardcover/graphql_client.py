import requests

from .config import GRAPHQL_URL, API_KEY


def gql(query: str, variables: dict | None = None) -> dict:
    headers = {
        "Content-Type": "application/json",
    }
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        resp = requests.post(GRAPHQL_URL, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError("Hardcover API request failed") from exc

    try:
        data = resp.json()
    except ValueError as exc:
        raise RuntimeError("Hardcover API returned invalid JSON") from exc

    if "errors" in data:
        raise RuntimeError("Hardcover API returned a GraphQL error")
    return data["data"]
