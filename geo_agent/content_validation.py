"""Deterministic pre-publish validation for generated content.

No LLM, no network — fast, testable rules that catch the failure classes that slipped
through to a live client in the Downtown Dental review:
  - credential claims (board-certified / diplomate / specialist / fellow) NOT backed by the
    verified provider profile (false-advertising landmine on YMYL sites),
  - marketing superlatives (best / #1 / premier / world-class …),
  - dangerous YMYL absolutes (painless / pain-free / guaranteed / "lasts a lifetime"),
  - future-dated "freshness" stamps (a "Last updated: <next month>" that hasn't happened).

This is the DETERMINISTIC layer. `geo_agent.fact_check` is the LLM semantic layer. Both run
at the publish gate; this one ALSO runs at DOCX render time, so content already stored in the
DB is checked before a human ships it — closing the bypass where the docx deliverable skipped
all validation.

`validate_html_claims()` is pure detection (no mutation) so it is safe to call on stored
content. `auto_soften()` performs the few mutations we are confident about and is only called
at generation time, before content is stored.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

# ── Finding severities ────────────────────────────────────────────────────────
BLOCK = "block"  # must not publish without a human fixing it
WARN = "warn"    # should review; not necessarily wrong


def _finding(severity: str, category: str, message: str) -> dict[str, str]:
    return {"severity": severity, "category": category, "message": message}


# ── Profile corpus (what credentials/specialties are actually verified) ───────
# ADA-recognized dental specialty stems — a provider holding one of these IS, by definition,
# a specialist, so a "specialist" claim is grounded when any of these appears in the profile.
_SPECIALTY_STEMS = (
    "prosthodont", "endodont", "periodont", "orthodont", "pediatric dent", "pedodont",
    "oral surg", "oral and maxillofacial", "oral medicine", "oral pathol", "oral radiol",
    "dental anesthesiol", "dental public health",
)


def _provider_corpus(customer: Any) -> str:
    """Lowercased blob of every verified credential/specialty/bio string for `customer`.

    Accepts a config `Customer` (with `.providers`) or a plain dict (DB shape). A credential
    claim in content is considered grounded only if its key token appears in this corpus.
    """
    parts: list[str] = []

    def _provs(obj: Any) -> list[Any]:
        if hasattr(obj, "providers"):
            return obj.providers or []
        if isinstance(obj, dict):
            return obj.get("providers") or []
        return []

    for p in _provs(customer):
        get = (lambda k: getattr(p, k, "")) if not isinstance(p, dict) else (lambda k: p.get(k, ""))
        parts.append(str(get("credentials") or ""))
        parts.append(str(get("bio") or ""))
        spec = get("specialties") or []
        parts.append(" ".join(spec) if isinstance(spec, (list, tuple)) else str(spec))
        # `affiliations` isn't on the dataclass but may ride along in a dict profile.
        if isinstance(p, dict):
            aff = p.get("affiliations") or []
            parts.append(" ".join(aff) if isinstance(aff, (list, tuple)) else str(aff))

    top_spec = getattr(customer, "specialties", None)
    if top_spec is None and isinstance(customer, dict):
        top_spec = customer.get("specialties")
    if top_spec:
        parts.append(" ".join(top_spec) if isinstance(top_spec, (list, tuple)) else str(top_spec))

    return " ".join(parts).lower()


# ── Rule tables ───────────────────────────────────────────────────────────────
# Credential claim → predicate(corpus) returning True when the claim is grounded.
_CREDENTIAL_RULES: list[tuple[str, str, Any]] = [
    (r"board[\s-]*certified", "board-certified",
     lambda c: bool(re.search(r"board[\s-]*certif", c))),
    (r"\bdiplomate\b", "diplomate", lambda c: "diplomate" in c),
    (r"\bfellowship[\s-]*trained\b", "fellowship-trained", lambda c: "fellow" in c),
    (r"\bspecialist\b", "specialist",
     lambda c: ("specialist" in c) or any(s in c for s in _SPECIALTY_STEMS)),
]

# Marketing superlatives — flagged for human review (never auto-edited; tone is subjective).
_SUPERLATIVES = [
    r"\bbest\b", r"#\s*1\b", r"\bnumber one\b", r"\bpremier\b", r"\bworld[\s-]*class\b",
    r"\btop[\s-]*rated\b", r"\bfinest\b", r"\bunmatched\b", r"\bunparalleled\b",
    r"\bmost trusted\b", r"\bleading\b",
]

# Dangerous YMYL absolutes — (pattern, replacement|None). None = flag only, no safe auto-fix.
_YMYL_ABSOLUTES: list[tuple[str, str | None]] = [
    (r"\bpain[\s-]*free\b", "gentle"),
    (r"\bpainless\b", "comfortable"),
    (r"\blasts? a lifetime\b", "lasts for decades with proper care"),
    (r"\blifetime of function\b", "decades of reliable function"),
    (r"\bguarantee[ds]?\b", None),
    (r"\bcompletely safe\b", None),
    (r"\bno risk\b", None),
]

_MONTHS = ("january february march april may june july august september october "
           "november december").split()
_MONTH_IDX = {m: i + 1 for i, m in enumerate(_MONTHS)}


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _future_dates(html: str, today: date | None = None) -> list[str]:
    """Return human-readable date strings in `html` that are AFTER today (deduped, in order)."""
    today = today or _today()
    found: list[str] = []
    seen: set[str] = set()

    def _add(label: str, d: date) -> None:
        if d > today and label not in seen:
            seen.add(label)
            found.append(label)

    # ISO dates, incl. inside <time datetime="YYYY-MM-DD"> attributes.
    for m in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b", html):
        y, mo, da = (int(g) for g in m.groups())
        try:
            _add(m.group(0), date(y, mo, da))
        except ValueError:
            continue
    # "Month YYYY" (e.g. "Last updated: August 2026"). Treat as the 1st of that month.
    for m in re.finditer(r"\b([A-Za-z]+)\s+(\d{4})\b", html):
        mo = _MONTH_IDX.get(m.group(1).lower())
        if mo:
            _add(m.group(0), date(int(m.group(2)), mo, 1))
    return found


# ── Public API ────────────────────────────────────────────────────────────────
def validate_html_claims(
    html: str,
    customer: Any,
    today: date | None = None,
) -> list[dict[str, str]]:
    """Return a list of findings for one HTML snippet. Pure detection — never mutates `html`.

    Each finding: {"severity": BLOCK|WARN, "category": str, "message": str}.
    An empty list means the snippet is clean by the deterministic rules.
    """
    if not html:
        return []
    findings: list[dict[str, str]] = []
    low = html.lower()
    corpus = _provider_corpus(customer)

    # 1) Credential grounding — the false-advertising landmine. BLOCK.
    for pat, label, grounded in _CREDENTIAL_RULES:
        if re.search(pat, low) and not grounded(corpus):
            findings.append(_finding(
                BLOCK, "credential",
                f"Claims '{label}' but no provider credential/specialty in the verified "
                f"profile supports it. Confirm with the client or remove the claim.",
            ))

    # 2) Dangerous YMYL absolutes. BLOCK.
    for pat, _repl in _YMYL_ABSOLUTES:
        m = re.search(pat, low)
        if m:
            findings.append(_finding(
                BLOCK, "ymyl-absolute",
                f"Contains the absolute/medical-guarantee phrase '{m.group(0)}' — unsafe on a "
                f"health/legal site. Soften or remove.",
            ))

    # 3) Marketing superlatives. WARN.
    hits = sorted({re.search(p, low).group(0) for p in _SUPERLATIVES if re.search(p, low)})
    if hits:
        findings.append(_finding(
            WARN, "superlative",
            "Unverifiable superlative(s): " + ", ".join(f"'{h}'" for h in hits)
            + ". Replace with specific, verifiable facts.",
        ))

    # 4) Future-dated content. BLOCK (a "freshness" date that hasn't happened reads as fake).
    fut = _future_dates(html, today)
    if fut:
        findings.append(_finding(
            BLOCK, "future-date",
            "Future date(s): " + ", ".join(fut) + ". Use today's date or earlier.",
        ))

    return findings


def auto_soften(html: str, today: date | None = None) -> tuple[str, list[str]]:
    """Apply the safe, confident mutations (generation-time only, before storage).

    Softens YMYL absolutes that have a safe replacement and rewrites obvious
    "Last updated: <future month year>" stamps to the current month. Returns
    (new_html, list_of_change_descriptions).
    """
    today = today or _today()
    changes: list[str] = []

    for pat, repl in _YMYL_ABSOLUTES:
        if repl is None:
            continue
        new = re.sub(pat, repl, html, flags=re.IGNORECASE)
        if new != html:
            changes.append(f"softened '{pat}' → '{repl}'")
            html = new

    # Rewrite "Last updated: <Month YYYY>" / "Updated <Month YYYY>" when that month is future.
    cur = f"{_MONTHS[today.month - 1].capitalize()} {today.year}"

    def _fix_month(m: re.Match) -> str:
        mo = _MONTH_IDX.get(m.group(2).lower())
        if mo and date(int(m.group(3)), mo, 1) > today:
            changes.append(f"future '{m.group(0).strip()}' → '{m.group(1)}{cur}'")
            return f"{m.group(1)}{cur}"
        return m.group(0)

    html = re.sub(
        r"((?:last\s+)?updated[:\s]+)([A-Za-z]+)\s+(\d{4})",
        _fix_month, html, flags=re.IGNORECASE,
    )
    return html, changes


def summarize(findings: list[dict[str, str]]) -> tuple[int, int]:
    """Return (block_count, warn_count) for a findings list."""
    b = sum(1 for f in findings if f.get("severity") == BLOCK)
    return b, len(findings) - b
