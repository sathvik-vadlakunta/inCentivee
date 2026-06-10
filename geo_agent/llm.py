"""Centralized Claude model configuration and safe completion helpers.

Bump model IDs HERE, not at call sites. The `complete()` helper streams
(avoiding HTTP timeouts at high max_tokens) and raises on truncation so callers
never silently accept or "repair" incomplete JSON that could ship to a client.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# --- Centralized model IDs ---------------------------------------------------
# Analysis/report generation (internal — scores are deterministic Python).
MODEL_ANALYSIS = "claude-opus-4-8"
# Content that gets PUBLISHED to clients' live sites (YMYL: medical/legal) —
# use the strongest model.
MODEL_CONTENT = "claude-opus-4-8"
# Cheap grounding/fact-check pass before publish.
MODEL_FACTCHECK = "claude-haiku-4-5"


class TruncatedResponseError(Exception):
    """The model hit max_tokens — output is incomplete and must NOT be trusted."""


def extract_text(message) -> str:
    """Concatenate text blocks, skipping thinking/tool blocks.

    Opus 4.6+ can emit a leading `thinking` block, so indexing `content[0].text`
    is unsafe — always filter by block type.
    """
    return "".join(
        b.text for b in message.content if getattr(b, "type", None) == "text"
    ).strip()


def complete(
    client,
    *,
    model: str,
    user: str,
    system: str | None = None,
    max_tokens: int = 16000,
    label: str = "",
) -> str:
    """Stream a single-turn completion and return its text.

    Streams (so large `max_tokens` don't hit the SDK's ~10-minute non-streaming
    timeout) and raises `TruncatedResponseError` if the model stopped on
    `max_tokens`, so callers fail loudly instead of accepting a cut-off response.
    """
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user}],
    }
    if system is not None:
        kwargs["system"] = system

    with client.messages.stream(**kwargs) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "max_tokens":
        raise TruncatedResponseError(
            f"{label or model} hit max_tokens={max_tokens}; output is incomplete "
            f"and was rejected (raise max_tokens or split the request)."
        )

    return extract_text(message)
