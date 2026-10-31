"""Gemini client shared by the agent, the RAG index and the eval judge."""

from functools import lru_cache

from google import genai
from google.genai import types

# Free-tier keys hit 429 quickly during evals; back off instead of failing the run.
RETRY = types.HttpRetryOptions(attempts=6, initial_delay=2.0, max_delay=60.0, http_status_codes=[429, 500, 503])


@lru_cache(maxsize=1)
def client() -> genai.Client:
    # Reads GEMINI_API_KEY (or GOOGLE_API_KEY) from the environment / .env
    return genai.Client(http_options=types.HttpOptions(retry_options=RETRY))


def thinking(model: str) -> types.ThinkingConfig | None:
    """Least thinking each model family allows: this is a latency-bound chat, not a puzzle."""
    if model.startswith("gemini-2.5-flash"):
        return types.ThinkingConfig(thinking_budget=0)
    if model.startswith("gemini-3"):
        return types.ThinkingConfig(thinking_level="low")
    return None
