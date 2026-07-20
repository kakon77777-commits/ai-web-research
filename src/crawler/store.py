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

_FRONTIER_SCHEMA = """
CREATE TABLE IF NOT EXISTS frontier (
    url TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    depth INTEGER NOT NULL,
    status TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_EXTRACTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS extractions (
    document_id TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    url TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    extracted_json TEXT NOT NULL,
    validation_errors TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (document_id, extractor_version)
);
"""

_RESEARCH_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seed TEXT NOT NULL,
    branches_json TEXT NOT NULL,
    compression_json TEXT NOT NULL,
    created_at TEXT NOT NULL
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


@dataclass
class ExtractionRecord:
    document_id: str
    extractor_version: str
    url: str
    provider: str
    model: str
    extracted_json: str
    validation_errors: str | None
    created_at: str


@dataclass
class ResearchRunRecord:
    seed: str
    branches_json: str
    compression_json: str
    created_at: str


class PageStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(_SCHEMA)
        self._conn.execute(_FRONTIER_SCHEMA)
        self._conn.execute(_EXTRACTIONS_SCHEMA)
        self._conn.execute(_RESEARCH_RUNS_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- persistent/resumable frontier -----------------------------------

    def frontier_mark_pending(self, url: str, domain: str, depth: int, now: str) -> None:
        """No-op if the URL is already tracked (any status) — a URL only
        ever needs to be queued once across the lifetime of a domain."""
        self._conn.execute(
            "INSERT OR IGNORE INTO frontier (url, domain, depth, status, discovered_at, updated_at) "
            "VALUES (?, ?, ?, 'pending', ?, ?)",
            (url, domain, depth, now, now),
        )
        self._conn.commit()

    def frontier_mark_done(self, url: str, now: str, status: str = "done") -> None:
        self._conn.execute(
            "UPDATE frontier SET status = ?, updated_at = ? WHERE url = ?",
            (status, now, url),
        )
        self._conn.commit()

    def frontier_urls_by_status(self, domain: str, status: str) -> list[tuple[str, int]]:
        cur = self._conn.execute(
            "SELECT url, depth FROM frontier WHERE domain = ? AND status = ? ORDER BY discovered_at ASC",
            (domain, status),
        )
        return cur.fetchall()

    def frontier_reset_domain(self, domain: str) -> None:
        self._conn.execute("DELETE FROM frontier WHERE domain = ?", (domain,))
        self._conn.commit()

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

    def pages_by_domain(self, domain: str) -> list[sqlite3.Row]:
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.execute(
            "SELECT * FROM pages WHERE domain = ? ORDER BY fetched_at ASC", (domain,)
        )
        return cur.fetchall()

    # -- semantic extraction (stage 4) ------------------------------------

    def save_extraction(self, record: ExtractionRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO extractions (
                document_id, extractor_version, url, provider, model,
                extracted_json, validation_errors, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id, extractor_version) DO UPDATE SET
                url=excluded.url,
                provider=excluded.provider,
                model=excluded.model,
                extracted_json=excluded.extracted_json,
                validation_errors=excluded.validation_errors,
                created_at=excluded.created_at
            """,
            (
                record.document_id, record.extractor_version, record.url, record.provider,
                record.model, record.extracted_json, record.validation_errors, record.created_at,
            ),
        )
        self._conn.commit()

    def get_extraction(self, document_id: str, extractor_version: str) -> sqlite3.Row | None:
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.execute(
            "SELECT * FROM extractions WHERE document_id = ? AND extractor_version = ?",
            (document_id, extractor_version),
        )
        return cur.fetchone()

    def pages_without_extraction(self, domain: str, extractor_version: str) -> list[sqlite3.Row]:
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.execute(
            """
            SELECT p.* FROM pages p
            LEFT JOIN extractions e
                ON e.document_id = p.document_id AND e.extractor_version = ?
            WHERE p.domain = ? AND e.document_id IS NULL
            ORDER BY p.fetched_at ASC
            """,
            (extractor_version, domain),
        )
        return cur.fetchall()

    # -- research runs (stage 5, DRC divergence/compression) --------------

    def save_research_run(self, record: ResearchRunRecord) -> int:
        cur = self._conn.execute(
            "INSERT INTO research_runs (seed, branches_json, compression_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            (record.seed, record.branches_json, record.compression_json, record.created_at),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_research_run(self, run_id: int) -> sqlite3.Row | None:
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,))
        return cur.fetchone()


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
