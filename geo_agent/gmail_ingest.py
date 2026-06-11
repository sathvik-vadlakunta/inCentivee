#!/usr/bin/env python3
"""Ingest email from the PracticeRank shared inbox into per-customer timelines.

Pulls recent messages, routes each to a customer by matching the other party's
address against the contacts table (and customer website domains), and files it
as a `customer_activities` row (de-duped by RFC Message-ID).

Two transports — Gmail API (OAuth, preferred) is used when a token is present,
otherwise IMAP (app password). Both feed the same parse/route/file logic.

Config (env, set in .env on the droplet — never committed):
    # OAuth (preferred)
    GMAIL_OAUTH_TOKEN_FILE   path to the stored token json (default data/gmail_token.json)
    GMAIL_CLIENT_SECRETS_FILE  OAuth client secrets json (only for --authorize)
    # IMAP (fallback)
    GMAIL_USER               e.g. kdoherty@practicerank.ai
    GMAIL_APP_PASSWORD       a Google App Password (NOT the account password)
    GMAIL_IMAP_HOST          optional, default imap.gmail.com

Usage:
    python -m geo_agent.gmail_ingest                       # sync last 30 days
    python -m geo_agent.gmail_ingest --days 7
    python -m geo_agent.gmail_ingest --test                # verify auth
    python -m geo_agent.gmail_ingest --authorize \\         # one-time OAuth (run locally)
        --client-secrets client_secret.json --token-out gmail_token.json
"""

from __future__ import annotations

import argparse
import email
import imaplib
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime

logger = logging.getLogger(__name__)

IMAP_HOST = os.environ.get("GMAIL_IMAP_HOST", "imap.gmail.com")
# Our own addresses — used to identify the "other party" and message direction.
_SELF_DOMAINS = {"practicerank.ai", "lostrelic.com"}

# Read-only Gmail access — we never modify the mailbox.
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
DEFAULT_TOKEN_FILE = os.environ.get(
    "GMAIL_OAUTH_TOKEN_FILE",
    str((__import__("pathlib").Path(__file__).resolve().parent.parent / "data" / "gmail_token.json")),
)

_MAILBOXES = [
    ("INBOX", "inbound"),
    ("[Gmail]/Sent Mail", "outbound"),
]


class GmailNotConfigured(RuntimeError):
    pass


def _creds() -> tuple[str, str]:
    user = os.environ.get("GMAIL_USER", "").strip()
    pw = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not user or not pw:
        raise GmailNotConfigured(
            "GMAIL_USER / GMAIL_APP_PASSWORD not set in environment."
        )
    return user, pw


def _connect() -> imaplib.IMAP4_SSL:
    user, pw = _creds()
    conn = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        conn.login(user, pw)
    except imaplib.IMAP4.error as e:
        raise GmailNotConfigured(
            f"Gmail IMAP login failed for {user}: {e}. "
            "Gmail requires an App Password (with 2-Step Verification on), not the "
            "account password. Create one at myaccount.google.com/apppasswords."
        ) from e
    return conn


def _decode(s: str | None) -> str:
    if not s:
        return ""
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return s


def _self_address(addr: str) -> bool:
    addr = (addr or "").lower()
    return any(addr.endswith("@" + d) or addr == d for d in _SELF_DOMAINS)


def _domain_of(addr: str) -> str:
    return addr.split("@", 1)[1].lower() if "@" in addr else ""


def _plain_body(msg: email.message.Message, limit: int = 4000) -> str:
    """Best-effort plain-text body, HTML stripped as a fallback, truncated."""
    text = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp:
                continue
            if ctype == "text/plain":
                text = _part_text(part)
                if text:
                    break
        if not text:  # no text/plain — fall back to stripped HTML
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    text = re.sub(r"<[^>]+>", " ", _part_text(part))
                    break
    else:
        text = _part_text(msg)
        if msg.get_content_type() == "text/html":
            text = re.sub(r"<[^>]+>", " ", text)

    # Trim quoted reply chains and signatures lightly, collapse whitespace.
    text = re.split(r"\nOn .*wrote:\n|\n-----Original Message-----", text)[0]
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:limit]


def _part_text(part: email.message.Message) -> str:
    try:
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    except Exception:
        return ""


def _route(addresses: list[str], index: dict) -> str | None:
    """Pick the customer for a message given all non-self addresses."""
    emails = index["emails"]
    domains = index["domains"]
    # Exact contact-email match first (most precise).
    for a in addresses:
        if a in emails:
            return emails[a]
    # Then business-domain match.
    for a in addresses:
        dom = _domain_of(a)
        if dom in domains:
            return domains[dom]
    return None


def _new_summary() -> dict:
    return {"filed": 0, "skipped_no_match": 0, "duplicates": 0, "scanned": 0, "errors": 0}


def _oauth_configured() -> bool:
    return os.path.exists(DEFAULT_TOKEN_FILE)


def sync(db, days: int = 30, limit_per_box: int = 500) -> dict:
    """Pull recent mail and file matched messages. Prefers Gmail API (OAuth)."""
    if _oauth_configured():
        return sync_api(db, days=days, max_messages=limit_per_box * 2)
    return sync_imap(db, days=days, limit_per_box=limit_per_box)


# ---------------------------------------------------------------- Gmail API (OAuth)

def _gmail_service():
    """Build an authorized Gmail API client from the stored OAuth token."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as e:
        raise GmailNotConfigured(
            "Gmail API libraries not installed (google-api-python-client, "
            "google-auth-oauthlib)."
        ) from e
    import json as _json
    if not os.path.exists(DEFAULT_TOKEN_FILE):
        raise GmailNotConfigured(
            f"OAuth token not found at {DEFAULT_TOKEN_FILE}. Run --authorize first."
        )
    info = _json.loads(open(DEFAULT_TOKEN_FILE).read())
    creds = Credentials.from_authorized_user_info(info, GMAIL_SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(DEFAULT_TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        else:
            raise GmailNotConfigured("OAuth token invalid and not refreshable; re-authorize.")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def sync_api(db, days: int = 30, max_messages: int = 1000) -> dict:
    """Pull recent mail via the Gmail API and file matched messages."""
    import base64
    index = db.get_email_customer_index()
    if not index["emails"] and not index["domains"]:
        logger.warning("No contact emails or customer domains to match against.")
    summary = _new_summary()
    service = _gmail_service()

    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y/%m/%d")
    query = f"after:{after}"
    ids: list[str] = []
    page_token = None
    while len(ids) < max_messages:
        resp = service.users().messages().list(
            userId="me", q=query, maxResults=min(500, max_messages - len(ids)),
            pageToken=page_token,
        ).execute()
        ids.extend(m["id"] for m in resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    for mid in ids:
        summary["scanned"] += 1
        try:
            msg = service.users().messages().get(userId="me", id=mid, format="raw").execute()
            raw = base64.urlsafe_b64decode(msg["raw"].encode("utf-8"))
            direction = "outbound" if "SENT" in (msg.get("labelIds") or []) else "inbound"
            parsed = email.message_from_bytes(raw)
            _file_message(parsed, direction, index, db, summary, fallback_id=mid)
        except Exception as e:
            summary["errors"] += 1
            logger.warning(f"  api message {mid} failed: {e}")

    logger.info(
        f"Gmail API sync: filed={summary['filed']} dupes={summary['duplicates']} "
        f"no_match={summary['skipped_no_match']} scanned={summary['scanned']} "
        f"errors={summary['errors']}"
    )
    return summary


def authorize(client_secrets_file: str, token_out: str) -> str:
    """One-time OAuth: open a browser, consent, write the token. Run locally."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as e:
        raise GmailNotConfigured("google-auth-oauthlib not installed.") from e
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, GMAIL_SCOPES)
    creds = flow.run_local_server(port=0)
    with open(token_out, "w") as f:
        f.write(creds.to_json())
    return token_out


# ---------------------------------------------------------------- IMAP (fallback)

def sync_imap(db, days: int = 30, limit_per_box: int = 500) -> dict:
    """Pull recent mail over IMAP (app password) and file matched messages."""
    index = db.get_email_customer_index()
    if not index["emails"] and not index["domains"]:
        logger.warning("No contact emails or customer domains to match against.")

    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
    summary = _new_summary()

    conn = _connect()
    try:
        for mailbox, direction in _MAILBOXES:
            try:
                status, _ = conn.select(f'"{mailbox}"', readonly=True)
                if status != "OK":
                    logger.info(f"Mailbox not found, skipping: {mailbox}")
                    continue
                status, data = conn.search(None, f'(SINCE {since})')
                if status != "OK":
                    continue
                uids = data[0].split()
                if len(uids) > limit_per_box:
                    uids = uids[-limit_per_box:]  # newest N
                for uid in uids:
                    summary["scanned"] += 1
                    try:
                        if _ingest_one(conn, uid, direction, index, db, summary):
                            pass
                    except Exception as e:
                        summary["errors"] += 1
                        logger.warning(f"  message {uid!r} failed: {e}")
            except Exception as e:
                logger.warning(f"Mailbox {mailbox} failed: {e}")
    finally:
        try:
            conn.logout()
        except Exception:
            pass
    logger.info(
        f"Gmail sync: filed={summary['filed']} dupes={summary['duplicates']} "
        f"no_match={summary['skipped_no_match']} scanned={summary['scanned']} "
        f"errors={summary['errors']}"
    )
    return summary


def _ingest_one(conn, uid, direction, index, db, summary) -> bool:
    status, msg_data = conn.fetch(uid, "(RFC822)")
    if status != "OK" or not msg_data or not msg_data[0]:
        summary["errors"] += 1
        return False
    msg = email.message_from_bytes(msg_data[0][1])
    return _file_message(msg, direction, index, db, summary, fallback_id=uid.decode())


def _file_message(msg, direction, index, db, summary, fallback_id: str = "") -> bool:
    """Route a parsed message to a customer and file it. Transport-agnostic."""
    from_pairs = getaddresses([msg.get("From", "")])
    to_pairs = getaddresses([msg.get("To", "")]) + getaddresses([msg.get("Cc", "")])
    from_addr = (from_pairs[0][1].lower() if from_pairs else "")
    all_addrs = [a.lower() for _, a in (from_pairs + to_pairs) if a]
    other_addrs = [a for a in all_addrs if not _self_address(a)]

    customer_id = _route(other_addrs, index)
    if not customer_id:
        summary["skipped_no_match"] += 1
        return False

    message_id = (msg.get("Message-ID") or "").strip() or f"uid:{fallback_id}"
    subject = _decode(msg.get("Subject")) or "(no subject)"
    body = _plain_body(msg)
    try:
        dt = parsedate_to_datetime(msg.get("Date"))
        created_at = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        created_at = None

    counterpart = from_addr if direction == "inbound" else (other_addrs[0] if other_addrs else "")
    row_id = db.add_customer_activity(
        customer_id,
        activity_type="email",
        subject=f"{'↘' if direction == 'inbound' else '↗'} {subject}",
        body=body,
        meta={"gmail_id": message_id, "from": from_addr, "direction": direction,
              "counterpart": counterpart},
        created_by="gmail-sync",
        created_at=created_at,
    )
    if row_id == 0:
        summary["duplicates"] += 1
        return False
    summary["filed"] += 1
    return True


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Ingest Gmail into customer timelines")
    parser.add_argument("--days", type=int, default=30, help="Look-back window (default 30)")
    parser.add_argument("--test", action="store_true", help="Verify auth and exit")
    parser.add_argument("--authorize", action="store_true", help="Run one-time OAuth (local browser)")
    parser.add_argument("--client-secrets", default=os.environ.get("GMAIL_CLIENT_SECRETS_FILE", ""))
    parser.add_argument("--token-out", default=DEFAULT_TOKEN_FILE)
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args()

    from geo_agent.db import CustomerDB

    if args.authorize:
        if not args.client_secrets:
            print("FAILED: provide --client-secrets path (OAuth client json).")
            return 1
        try:
            out = authorize(args.client_secrets, args.token_out)
            print(f"OK: token written to {out}")
            return 0
        except Exception as e:
            print(f"FAILED: {e}")
            return 1

    if args.test:
        try:
            if _oauth_configured():
                svc = _gmail_service()
                prof = svc.users().getProfile(userId="me").execute()
                print(f"OK: Gmail API authorized as {prof.get('emailAddress')}.")
            else:
                conn = _connect()
                conn.logout()
                print("OK: Gmail IMAP login succeeded.")
            return 0
        except GmailNotConfigured as e:
            print(f"FAILED: {e}")
            return 1

    db = CustomerDB(db_path=args.db_path)
    try:
        summary = sync(db, days=args.days)
        print(summary)
        return 0
    except GmailNotConfigured as e:
        print(f"FAILED: {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
