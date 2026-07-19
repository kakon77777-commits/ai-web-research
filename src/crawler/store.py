"""SQLite metadata store + raw/parsed file writer.

Table schema mirrors the page-record model in the project doc (section 33).
content_hash drives "only re-process changed pages" behaviour on re-crawl
(Appendix C, step 9).
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

PARSER_VERSION = "ai-web-research-stage1/0.1.0"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    document_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    canonical_url TEXT,
    domain TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    published_at TEXT,
    status_code INTEGER,
    content_type TEXT,
    raw_path TEXT,
    markdown_path TEXT,
    content_hash TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    language TEXT,
    title TEXT,
    author TEXT,
    license_hint TEXT,
    robots_allowed INTEGER NOT NULL,
    unchanged_since TEXT
);
"""


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def document_id_for(url: str) -> str:
    return sha256_hex(url)


@dataclass
class PageRecord:
    url: str
    canonical_url: str | None
    domain: str
    fetched_at: str
    published_at: str | None
    status_code: int | None
    content_type: str
    raw_path: str | None
    markdown_path: str | None
    content_hash: str
    language: str | None
    title: str | None
    author: str | None
    license_hint: str | None
    robots_allowed: bool


class PageStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def previous_hash(self, url: str) -> str | None:
        cur = self._conn.execute(
            "SELECT content_hash FROM pages WHERE document_id = ?",
            (document_id_for(url),),
        )
        row = cur.fetchone()
        return row[0] if row else None

    def upsert(self, record: PageRecord, unchanged: bool) -> None:
        doc_id = document_id_for(record.url)
        previous = self._conn.execute(
            "SELECT unchanged_since FROM pages WHERE document_id = ?", (doc_id,)
        ).fetchone()
        unchanged_since = None
        if unchanged:
            unchanged_since = previous[0] if previous and previous[0] else record.fetched_at

        self._conn.execute(
            """
            INSERT INTO pages (
                document_id, url, canonical_url, domain, fetched_at, published_at,
                status_code, content_type, raw_path, markdown_path, content_hash,
                parser_version, language, title, author, license_hint, robots_allowed,
                unchanged_since
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                url=excluded.url,
                canonical_url=excluded.canonical_url,
                fetched_at=excluded.fetched_at,
                published_at=excluded.published_at,
                status_code=excluded.status_code,
                content_type=excluded.content_type,
                raw_path=excluded.raw_path,
                markdown_path=excluded.markdown_path,
                content_hash=excluded.content_hash,
                parser_version=excluded.parser_version,
                language=excluded.language,
                title=excluded.title,
                author=excluded.author,
                license_hint=excluded.license_hint,
                robots_allowed=excluded.robots_allowed,
                unchanged_since=excluded.unchanged_since
            """,
            (
                doc_id, record.url, record.canonical_url, record.domain, record.fetched_at,
                record.published_at, record.status_code, record.content_type, record.raw_path,
                record.markdown_path, record.content_hash, PARSER_VERSION, record.language,
                record.title, record.author, record.license_hint, int(record.robots_allowed),
                unchanged_since,
            ),
        )
        self._conn.commit()

    def all_pages(self) -> list[sqlite3.Row]:
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.execute("SELECT * FROM pages ORDER BY fetched_at DESC")
        return cur.fetchall()


def write_raw(raw_dir: Path, domain: str, doc_id: str, html: str) -> Path:
    target_dir = raw_dir / domain
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{doc_id}.html"
    path.write_text(html, encoding="utf-8")
    return path


def write_parsed(parsed_dir: Path, domain: str, doc_id: str, markdown: str) -> Path:
    target_dir = parsed_dir / domain
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{doc_id}.md"
    path.write_text(markdown, encoding="utf-8")
    return path
