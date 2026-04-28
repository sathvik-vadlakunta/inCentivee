"""Embedding client using Voyage AI (Anthropic's recommended partner).

Each call creates a fresh client — no global state that could leak
between customers.
"""

from __future__ import annotations

import os

import voyageai


def _new_client() -> voyageai.Client:
    """Create a fresh Voyage AI client (no singleton/caching)."""
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        raise ValueError("VOYAGE_API_KEY environment variable required")
    return voyageai.Client(api_key=api_key)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using Voyage AI.

    Uses voyage-3.5-lite (1024 dims) — good balance of quality and cost.
    Max batch size is 128 texts, max 32K tokens per text.
    """
    client = _new_client()
    # Batch in chunks of 128
    all_embeddings = []
    for i in range(0, len(texts), 128):
        batch = texts[i : i + 128]
        result = client.embed(batch, model="voyage-3.5-lite", input_type="document")
        all_embeddings.extend(result.embeddings)
    return all_embeddings


def embed_query(text: str) -> list[float]:
    """Embed a single search query."""
    client = _new_client()
    result = client.embed([text], model="voyage-3.5-lite", input_type="query")
    return result.embeddings[0]
