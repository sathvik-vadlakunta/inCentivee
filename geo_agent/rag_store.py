"""Per-customer RAG store using SQLite + sqlite-vec + FTS5.

One .db file per customer for natural multi-tenant isolation.
Hybrid search: vector similarity (sqlite-vec) + keyword (FTS5).
Supports optional encryption at rest via SQLCipher.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import struct
from datetime import datetime, timezone
from pathlib import Path

import sqlite_vec

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 1024  # voyage-3.5-lite dimensions


def _serialize_f32(vec: list[float]) -> bytes:
    """Pack float list into bytes for sqlite-vec."""
    return struct.pack(f"{len(vec)}f", *vec)


def _get_encryption_key() -> str | None:
    """Get the database encryption key from environment.

    Set DB_ENCRYPTION_KEY to enable SQLCipher encryption at rest.
    All customer databases use the same key (key is per-deployment, not per-customer).
    """
    return os.environ.get("DB_ENCRYPTION_KEY")


class CustomerRAG:
    """RAG store for a single dental practice customer."""

    def __init__(self, customer_id: str, data_dir: str = "/app/data/customers"):
        self.customer_id = customer_id
        self.db_path = Path(data_dir) / f"{customer_id}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        encryption_key = _get_encryption_key()

        if encryption_key:
            try:
                from pysqlcipher3 import dbapi2 as sqlcipher
                self.db = sqlcipher.connect(str(self.db_path))
                self.db.execute(f"PRAGMA key='{encryption_key}'")
                logger.info(f"Opened encrypted database for {customer_id}")
            except ImportError:
                logger.warning("pysqlcipher3 not installed — falling back to unencrypted SQLite")
                self.db = sqlite3.connect(str(self.db_path))
        else:
            self.db = sqlite3.connect(str(self.db_path))

        self.db.enable_load_extension(True)
        sqlite_vec.load(self.db)
        self.db.enable_load_extension(False)
        self._init_schema()

    def _init_schema(self):
        self.db.executescript(f"""
            CREATE TABLE IF NOT EXISTS pages (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT,
                content TEXT NOT NULL,
                category TEXT,
                metadata TEXT DEFAULT '{{}}',
                updated_at TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS pages_vec USING vec0 (
                id TEXT PRIMARY KEY,
                embedding FLOAT[{EMBEDDING_DIM}]
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5 (
                title, content, category,
                content=pages, content_rowid=rowid,
                tokenize='porter unicode61'
            );

            CREATE TABLE IF NOT EXISTS run_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT NOT NULL,
                changes_made TEXT,
                llms_txt_version TEXT,
                schema_updates TEXT
            );
        """)
        self.db.commit()

    def upsert_page(
        self,
        page_id: str,
        url: str,
        title: str,
        content: str,
        embedding: list[float],
        category: str = "page",
        metadata: dict | None = None,
    ):
        """Insert or update a page with its embedding."""
        now = datetime.now(timezone.utc).isoformat()
        meta_json = json.dumps(metadata or {})

        # Upsert the page content
        self.db.execute(
            """INSERT OR REPLACE INTO pages (id, url, title, content, category, metadata, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (page_id, url, title, content, category, meta_json, now),
        )

        # Upsert the vector embedding
        self.db.execute("DELETE FROM pages_vec WHERE id = ?", (page_id,))
        self.db.execute(
            "INSERT INTO pages_vec (id, embedding) VALUES (?, ?)",
            (page_id, _serialize_f32(embedding)),
        )

        # Rebuild FTS index for this row
        rowid = self.db.execute(
            "SELECT rowid FROM pages WHERE id = ?", (page_id,)
        ).fetchone()[0]
        self.db.execute(
            "INSERT OR REPLACE INTO pages_fts (rowid, title, content, category) VALUES (?, ?, ?, ?)",
            (rowid, title, content, category),
        )
        self.db.commit()

    def search(
        self,
        query_text: str,
        query_embedding: list[float],
        n: int = 10,
    ) -> list[dict]:
        """Hybrid search: vector similarity + keyword matching with rank fusion."""
        # Vector search
        vec_rows = self.db.execute(
            """SELECT id, distance FROM pages_vec
               WHERE embedding MATCH ? ORDER BY distance LIMIT ?""",
            (_serialize_f32(query_embedding), n * 2),
        ).fetchall()

        # Keyword search
        fts_rows = self.db.execute(
            """SELECT pages.id, pages_fts.rank
               FROM pages_fts
               JOIN pages ON pages.rowid = pages_fts.rowid
               WHERE pages_fts MATCH ?
               ORDER BY pages_fts.rank LIMIT ?""",
            (query_text, n * 2),
        ).fetchall()

        # Reciprocal Rank Fusion
        scores: dict[str, float] = {}
        k = 60  # RRF constant
        for rank, (page_id, _) in enumerate(vec_rows):
            scores[page_id] = scores.get(page_id, 0) + 1.0 / (k + rank + 1)
        for rank, (page_id, _) in enumerate(fts_rows):
            scores[page_id] = scores.get(page_id, 0) + 1.0 / (k + rank + 1)

        # Get full page data for top results
        top_ids = sorted(scores, key=scores.get, reverse=True)[:n]
        results = []
        for page_id in top_ids:
            row = self.db.execute(
                "SELECT id, url, title, content, category, metadata FROM pages WHERE id = ?",
                (page_id,),
            ).fetchone()
            if row:
                results.append({
                    "id": row[0],
                    "url": row[1],
                    "title": row[2],
                    "content": row[3],
                    "category": row[4],
                    "metadata": json.loads(row[5]),
                    "score": scores[page_id],
                })
        return results

    def get_all_pages(self) -> list[dict]:
        """Get all stored pages for this customer."""
        rows = self.db.execute(
            "SELECT id, url, title, content, category, metadata FROM pages ORDER BY category, title"
        ).fetchall()
        return [
            {
                "id": r[0], "url": r[1], "title": r[2],
                "content": r[3], "category": r[4], "metadata": json.loads(r[5]),
            }
            for r in rows
        ]

    def log_run(self, changes: str, llms_txt: str, schema_updates: str):
        """Record a run in history for tracking."""
        self.db.execute(
            "INSERT INTO run_history (run_date, changes_made, llms_txt_version, schema_updates) VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), changes, llms_txt, schema_updates),
        )
        self.db.commit()

    def close(self):
        self.db.close()
