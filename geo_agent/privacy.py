"""PII protection utilities for external API calls.

Minimizes personally identifiable information sent to third-party services
(Voyage AI, etc.) while preserving data utility.
"""

from __future__ import annotations

import hashlib
import re


def hash_pii(value: str, prefix: str = "") -> str:
    """One-way hash of PII for use in external contexts.

    Returns a deterministic but irreversible identifier.
    """
    if not value:
        return ""
    h = hashlib.sha256(value.encode()).hexdigest()[:10]
    return f"{prefix}{h}" if prefix else h


def redact_phone(text: str) -> str:
    """Replace phone numbers with [PHONE] in text."""
    return re.sub(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", "[PHONE]", text)


def redact_address(text: str) -> str:
    """Replace street addresses with [ADDRESS] in text."""
    return re.sub(
        r"\d+\s+[A-Z][a-zA-Z\s]+(?:St|Ave|Blvd|Dr|Rd|Way|Ln|Ct|Pl|Pkwy|Circle|Suite|Ste)[.\s,]*",
        "[ADDRESS] ",
        text,
    )


def minimize_for_embedding(text: str) -> str:
    """Strip PII from text before sending to embedding services.

    Keeps the semantic content (dental services, procedures, etc.)
    but removes phone numbers and street addresses.
    """
    text = redact_phone(text)
    text = redact_address(text)
    return text
