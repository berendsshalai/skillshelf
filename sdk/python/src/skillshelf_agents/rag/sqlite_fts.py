from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel


class Citation(BaseModel):
    document_id: str
    source: str
    version: str
    section: str
    effective_at: datetime
    ingested_at: datetime
    retrieved_at: datetime
    content_hash: str
    freshness: str


class SearchResult(BaseModel):
    text: str
    score: float
    citation: Citation


class SQLiteKnowledgeBase:
    def __init__(self, path: Path | str) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS knowledge_documents(
              id TEXT PRIMARY KEY, source TEXT NOT NULL, version TEXT NOT NULL,
              effective_at TEXT NOT NULL, ingested_at TEXT NOT NULL, content_hash TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks USING fts5(
              document_id UNINDEXED, section UNINDEXED, text, tokenize='unicode61'
            );
            """
        )

    def close(self) -> None:
        self.connection.close()

    def ingest(
        self,
        *,
        document_id: str,
        source: str,
        version: str,
        effective_at: datetime,
        ingested_at: datetime,
        sections: dict[str, str],
    ) -> str:
        canonical = "\n".join(f"{name}\n{sections[name].strip()}" for name in sorted(sections))
        content_hash = hashlib.sha256(canonical.encode()).hexdigest()
        with self.connection:
            self.connection.execute("DELETE FROM knowledge_chunks WHERE document_id=?", (document_id,))
            self.connection.execute(
                "INSERT OR REPLACE INTO knowledge_documents VALUES(?,?,?,?,?,?)",
                (
                    document_id, source, version, effective_at.isoformat(),
                    ingested_at.isoformat(), content_hash,
                ),
            )
            for section in sorted(sections):
                paragraphs = [part.strip() for part in sections[section].split("\n\n") if part.strip()]
                for paragraph in paragraphs:
                    self.connection.execute(
                        "INSERT INTO knowledge_chunks VALUES(?,?,?)",
                        (document_id, section, paragraph),
                    )
        return content_hash

    def search(self, query: str, *, retrieved_at: datetime, limit: int = 5) -> list[SearchResult]:
        rows = self.connection.execute(
            """
            SELECT c.document_id,c.section,c.text,bm25(knowledge_chunks) AS rank,
                   d.source,d.version,d.effective_at,d.ingested_at,d.content_hash
            FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id
            WHERE knowledge_chunks MATCH ?
            ORDER BY rank,c.document_id,c.section LIMIT ?
            """,
            (query, limit),
        ).fetchall()
        output: list[SearchResult] = []
        now = retrieved_at.astimezone(UTC)
        for row in rows:
            effective = datetime.fromisoformat(row["effective_at"])
            ingested = datetime.fromisoformat(row["ingested_at"])
            age_days = (now - effective.astimezone(UTC)).days
            freshness = "current" if age_days <= 30 else "aging" if age_days <= 180 else "stale"
            output.append(
                SearchResult(
                    text=row["text"],
                    score=-float(row["rank"]),
                    citation=Citation(
                        document_id=row["document_id"],
                        source=row["source"],
                        version=row["version"],
                        section=row["section"],
                        effective_at=effective,
                        ingested_at=ingested,
                        retrieved_at=retrieved_at,
                        content_hash=row["content_hash"],
                        freshness=freshness,
                    ),
                )
            )
        return output
