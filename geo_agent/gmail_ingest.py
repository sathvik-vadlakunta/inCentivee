#!/usr/bin/env python3
"""Ingest email from the PracticeRank shared inbox into per-customer timelines.

Connects to Gmail over IMAP (app password), pulls recent messages from INBOX and
Sent Mail, routes each to a customer by matching the other party's address against
the contacts table (and customer website domains), and files it as a
`customer_activities` row (de-duped by RFC Message-ID).

Config (env, set in .env on the droplet — never committed):
    GMAIL_USER            e.g. kdoherty@practicerank.ai
    GMAIL_APP_PASSWORD    a Google App Password (NOT the account password)
    GMAIL_IMAP_HOST       optional, default imap.gmail.com

Usage:
    python -m geo_agent.gmail_ingest               # sync last 30 days
    python -m geo_agent.gmail_ingest --days 7
    python -m geo_agent.gmail_ingest --test        # just verify login
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


def sync(db, days: int = 30, limit_per_box: int = 500) -> dict:
    """Pull recent mail and file matched messages to customer timelines.

    Returns a summary dict: {filed, skipped_no_match, duplicates, scanned, errors}.
    """
    index = db.get_email_customer_index()
    if not index["emails"] and not index["domains"]:
        logger.warning("No contact emails or customer domains to match against.")

    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
    summary = {"filed": 0, "skipped_no_match": 0, "duplicates": 0, "scanned": 0, "errors": 0}

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

    from_pairs = getaddresses([msg.get("From", "")])
    to_pairs = getaddresses([msg.get("To", "")]) + getaddresses([msg.get("Cc", "")])
    from_addr = (from_pairs[0][1].lower() if from_pairs else "")
    all_addrs = [a.lower() for _, a in (from_pairs + to_pairs) if a]
    other_addrs = [a for a in all_addrs if not _self_address(a)]

    customer_id = _route(other_addrs, index)
    if not customer_id:
        summary["skipped_no_match"] += 1
        return False

    message_id = (msg.get("Message-ID") or "").strip() or f"uid:{uid.decode()}"
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
    parser.add_argument("--test", action="store_true", help="Verify IMAP login and exit")
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args()

    from geo_agent.db import CustomerDB

    if args.test:
        try:
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
