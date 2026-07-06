"""Live AI-spend sync for the Expenses ledger.

Pulls real month-to-date **cost** (not token counts) from each provider's billing
API and writes it onto that month's seeded expense row (by template_key). These
require a provider **admin / org billing key** — distinct from the inference key
used to call the models — set in the droplet's `.env`:

    ANTHROPIC_ADMIN_KEY   sk-ant-admin...   (Anthropic Cost API)
    OPENAI_ADMIN_KEY      sk-...            (OpenAI Costs API, org admin key)
    GEMINI_COST_CMD / GCP billing export     (see fetch_gemini_cost)

Anthropic + OpenAI are wired end-to-end. Gemini needs a Google Cloud Billing
export (BigQuery) to expose dollar spend — stubbed until that's set up.
Perplexity and xAI (Grok) have no public cost API today, so they stay manual.

Everything is defensive: a missing key or an API error degrades to a per-provider
status string and never breaks the page — the amount just stays manual.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

_TIMEOUT = 25


def _http_get_json(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read().decode())


def _month_bounds(month: str) -> tuple[str, str]:
    """('YYYY-MM') -> ('YYYY-MM-01', first day of next month 'YYYY-MM-01')."""
    y, m = int(month[:4]), int(month[5:7])
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{month}-01", f"{ny:04d}-{nm:02d}-01"


def _unix(day: str) -> int:
    return int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


# --------------------------------------------------------------------------- #
# Provider fetchers — each returns dollars (float) for the given month.        #
# --------------------------------------------------------------------------- #
def fetch_anthropic_cost(month: str, admin_key: str) -> float:
    """Anthropic Admin Cost API — sums USD cost across daily buckets."""
    start, end = _month_bounds(month)
    url = ("https://api.anthropic.com/v1/organizations/cost_report"
           f"?starting_at={start}T00:00:00Z&ending_at={end}T00:00:00Z&bucket_width=1d")
    headers = {"x-api-key": admin_key, "anthropic-version": "2023-06-01"}
    total = 0.0
    for _ in range(40):  # paginate defensively
        data = _http_get_json(url, headers)
        for bucket in data.get("data", []):
            for res in bucket.get("results", []):
                # cost is a decimal-USD string ("amount") or {amount:{value}}
                amt = res.get("amount")
                if isinstance(amt, dict):
                    amt = amt.get("value")
                total += float(amt or 0)
        nxt = data.get("next_page")
        if data.get("has_more") and nxt:
            url = ("https://api.anthropic.com/v1/organizations/cost_report"
                   f"?starting_at={start}T00:00:00Z&ending_at={end}T00:00:00Z"
                   f"&bucket_width=1d&page={nxt}")
        else:
            break
    return round(total, 2)


def fetch_openai_cost(month: str, admin_key: str) -> float:
    """OpenAI Organization Costs API — sums USD across daily buckets."""
    start, end = _month_bounds(month)
    st, et = _unix(start), _unix(end)
    total, page = 0.0, None
    headers = {"Authorization": f"Bearer {admin_key}"}
    for _ in range(60):
        url = ("https://api.openai.com/v1/organizations/costs"
               f"?start_time={st}&end_time={et}&bucket_width=1d&limit=180")
        if page:
            url += f"&page={page}"
        data = _http_get_json(url, headers)
        for bucket in data.get("data", []):
            for res in bucket.get("results", []):
                amt = res.get("amount", {})
                total += float((amt or {}).get("value", 0) or 0)
        if data.get("has_more") and data.get("next_page"):
            page = data["next_page"]
        else:
            break
    return round(total, 2)


def fetch_gemini_cost(month: str, admin_key: str) -> float:
    """Google Gemini spend comes from Cloud Billing, not the Gemini API itself.
    Requires a BigQuery billing export + service account — not configured yet."""
    raise NotImplementedError("Gemini cost needs a Google Cloud Billing export (BigQuery).")


# key -> (env var holding the admin/billing key, fetcher)
PROVIDERS: dict[str, tuple[str, callable]] = {
    "anthropic": ("ANTHROPIC_ADMIN_KEY", fetch_anthropic_cost),
    "openai": ("OPENAI_ADMIN_KEY", fetch_openai_cost),
    "gemini": ("GEMINI_ADMIN_KEY", fetch_gemini_cost),
}


def sync_ai_usage(db, month: str) -> dict:
    """For each wired provider, pull month cost and write it onto the seeded
    ledger row (template_key == provider). Returns a per-provider status dict."""
    out: dict[str, dict] = {}
    for key, (env_name, fn) in PROVIDERS.items():
        api_key = (os.environ.get(env_name) or "").strip()
        if not api_key:
            out[key] = {"status": "no_key", "env": env_name}
            continue
        try:
            amount = fn(month, api_key)
        except NotImplementedError as e:
            out[key] = {"status": "unsupported", "detail": str(e)}
            continue
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError) as e:
            out[key] = {"status": "error", "detail": str(e)[:180]}
            continue
        note = f"Auto-synced from the {key} cost API on {datetime.now(timezone.utc):%Y-%m-%d}."
        updated = db.set_expense_amount_by_template(month, key, amount, note=note)
        out[key] = {"status": "ok" if updated else "no_row", "amount": amount}
    return out


def summarize(results: dict) -> str:
    """One-line human summary for the flash banner."""
    parts = []
    for k, r in results.items():
        s = r["status"]
        if s == "ok":
            parts.append(f"{k} ${r['amount']:,.2f}")
        elif s == "no_key":
            parts.append(f"{k}: no admin key")
        elif s == "unsupported":
            parts.append(f"{k}: needs Cloud Billing export")
        elif s == "no_row":
            parts.append(f"{k}: no seeded row this month")
        else:
            parts.append(f"{k}: error")
    return " · ".join(parts)
