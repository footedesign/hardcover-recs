import os

from .runtime import load_dotenv

load_dotenv()

GRAPHQL_URL = os.environ.get("HARDCOVER_GRAPHQL_URL")
API_KEY = os.environ.get("HARDCOVER_API_KEY")

if not GRAPHQL_URL:
    raise RuntimeError("HARDCOVER_GRAPHQL_URL is not set")
