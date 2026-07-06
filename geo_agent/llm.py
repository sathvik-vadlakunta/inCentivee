"""Centralized Claude model configuration and safe completion helpers.

Bump model IDs HERE, not at call sites. The `complete()` helper streams
(avoiding HTTP timeouts at high max_tokens) and raises on truncation so callers
never silently accept or "repair" incomplete JSON that could ship to a client.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# --- Centralized model IDs ---------------------------------------------------
# Tiered by cost vs. impact. Each is overridable via an env var of the same name
# (set in the droplet .env), so you can A/B a tier or instantly revert one to
# Opus without a code change/deploy. Bump the DEFAULTS here, not at call sites.
#
#   Opus 4.8  — anything PUBLISHED as client content (highest impact): the
#               blog/service page body, GBP Q&A, and expert quotes (YMYL).
#   Sonnet 5  — internal-only work: audit-report narration + service scraping.
#   Haiku 4.5 — cheap grounding / fact-check pass.
#
# Published client content — strongest model (page body, GBP Q&A, quotes).
MODEL_CONTENT = os.environ.get("MODEL_CONTENT", "claude-opus-4-8")
# Internal audit-report narration (scores are deterministic Python; the LLM only
# writes the prose around them). The main Opus→Sonnet cost win — A/B this one.
MODEL_ANALYSIS = os.environ.get("MODEL_ANALYSIS", "claude-sonnet-5")
# Internal data extraction (service scraping) — not client-facing.
MODEL_AUX = os.environ.get("MODEL_AUX", "claude-sonnet-5")
# Cheap grounding/fact-check pass before publish.
MODEL_FACTCHECK = os.environ.get("MODEL_FACTCHECK", "claude-haiku-4-5")


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
    output_schema: dict | None = None,
    label: str = "",
) -> str:
    """Stream a single-turn completion and return its text.

    Streams (so large `max_tokens` don't hit the SDK's ~10-minute non-streaming
    timeout) and raises `TruncatedResponseError` if the model stopped on
    `max_tokens`, so callers fail loudly instead of accepting a cut-off response.

    If `output_schema` (a JSON Schema object) is given, the model is constrained
    to emit JSON matching it (`output_config.format`) — the returned text is then
    guaranteed-valid JSON, so callers can `json.loads` directly with no fence
    stripping or repair.
    """
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user}],
    }
    if system is not None:
        kwargs["system"] = system
    if output_schema is not None:
        kwargs["output_config"] = {
            "format": {"type": "json_schema", "schema": output_schema}
        }

    with client.messages.stream(**kwargs) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "max_tokens":
        raise TruncatedResponseError(
            f"{label or model} hit max_tokens={max_tokens}; output is incomplete "
            f"and was rejected (raise max_tokens or split the request)."
        )

    return extract_text(message)
