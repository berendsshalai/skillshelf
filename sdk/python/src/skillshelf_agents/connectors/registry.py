from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from .contracts import ConnectorManifest


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class ConnectorRecord(BaseModel):
    id: str
    manifest: ConnectorManifest
    activation_state: Literal["INACTIVE", "ACTIVE", "DISABLED", "INACTIVE_REVIEW_REQUIRED"]
    last_test: dict[str, Any] | None = None
    last_sync: dict[str, Any] | None = None
    schema_digest: str
    secret_readiness: Literal["READY", "MISSING", "NOT_REQUIRED"]
    provider_health: Literal["UNKNOWN", "PASS", "DEGRADED", "FAIL"]
    created_at: datetime
    updated_at: datetime


class ConnectorRegistry:
    """Durable registry for connector configuration and operational state."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS connectors (
              id TEXT PRIMARY KEY,
              manifest_json TEXT NOT NULL,
              activation_state TEXT NOT NULL,
              last_test_json TEXT,
              last_sync_json TEXT,
              schema_digest TEXT NOT NULL,
              secret_readiness TEXT NOT NULL,
              provider_health TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS connector_cursors (
              connector_id TEXT NOT NULL,
              resource_id TEXT NOT NULL,
              cursor TEXT,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(connector_id, resource_id),
              FOREIGN KEY(connector_id) REFERENCES connectors(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS connector_raw_records (
              id INTEGER PRIMARY KEY,
              connector_id TEXT NOT NULL,
              resource_id TEXT NOT NULL,
              external_id TEXT NOT NULL,
              content_hash TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              observed_at TEXT NOT NULL,
              UNIQUE(connector_id, resource_id, external_id, content_hash)
            );
            CREATE TABLE IF NOT EXISTS connector_canonical_records (
              connector_id TEXT NOT NULL,
              resource_id TEXT NOT NULL,
              external_id TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              content_hash TEXT NOT NULL,
              observed_at TEXT NOT NULL,
              PRIMARY KEY(connector_id, resource_id, external_id, content_hash)
            );
            CREATE TABLE IF NOT EXISTS connector_quarantines (
              id INTEGER PRIMARY KEY,
              connector_id TEXT NOT NULL,
              resource_id TEXT NOT NULL,
              external_id TEXT NOT NULL,
              reason TEXT NOT NULL,
              payload_hash TEXT NOT NULL,
              observed_at TEXT NOT NULL
            );
            """
        )

    @staticmethod
    def _digest(manifest: ConnectorManifest) -> str:
        payload = _json(manifest.model_dump(mode="json"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def add(
        self,
        manifest: ConnectorManifest,
        *,
        activation_state: Literal["INACTIVE", "ACTIVE", "DISABLED", "INACTIVE_REVIEW_REQUIRED"] = "INACTIVE",
        now: datetime | None = None,
    ) -> ConnectorRecord:
        at = now or datetime.now(UTC)
        ready = "NOT_REQUIRED" if not manifest.secret_references else "MISSING"
        try:
            with self.connection:
                self.connection.execute(
                    "INSERT INTO connectors VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        manifest.id,
                        manifest.model_dump_json(),
                        activation_state,
                        None,
                        None,
                        self._digest(manifest),
                        ready,
                        "UNKNOWN",
                        at.isoformat(),
                        at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError(f"connector already exists: {manifest.id}") from error
        return self.inspect(manifest.id)

    def update(
        self,
        connector_id: str,
        *,
        manifest: ConnectorManifest | None = None,
        activation_state: Literal["INACTIVE", "ACTIVE", "DISABLED", "INACTIVE_REVIEW_REQUIRED"] | None = None,
        now: datetime | None = None,
    ) -> ConnectorRecord:
        current = self.inspect(connector_id)
        updated_manifest = manifest or current.manifest
        if updated_manifest.id != connector_id:
            raise ValueError("connector ID cannot be changed")
        at = now or datetime.now(UTC)
        with self.connection:
            self.connection.execute(
                """UPDATE connectors SET manifest_json=?,activation_state=?,schema_digest=?,
                   updated_at=? WHERE id=?""",
                (
                    updated_manifest.model_dump_json(),
                    activation_state or current.activation_state,
                    self._digest(updated_manifest),
                    at.isoformat(),
                    connector_id,
                ),
            )
        return self.inspect(connector_id)

    def inspect(self, connector_id: str) -> ConnectorRecord:
        row = self.connection.execute("SELECT * FROM connectors WHERE id=?", (connector_id,)).fetchone()
        if row is None:
            raise KeyError(connector_id)
        return ConnectorRecord(
            id=row["id"],
            manifest=ConnectorManifest.model_validate_json(row["manifest_json"]),
            activation_state=row["activation_state"],
            last_test=json.loads(row["last_test_json"]) if row["last_test_json"] else None,
            last_sync=json.loads(row["last_sync_json"]) if row["last_sync_json"] else None,
            schema_digest=row["schema_digest"],
            secret_readiness=row["secret_readiness"],
            provider_health=row["provider_health"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list(self) -> list[ConnectorRecord]:
        ids = [str(row[0]) for row in self.connection.execute("SELECT id FROM connectors ORDER BY id")]
        return [self.inspect(connector_id) for connector_id in ids]

    def delete(self, connector_id: str) -> None:
        with self.connection:
            deleted = self.connection.execute("DELETE FROM connectors WHERE id=?", (connector_id,)).rowcount
        if not deleted:
            raise KeyError(connector_id)

    def load(self, connector_id: str) -> ConnectorManifest:
        return self.inspect(connector_id).manifest

    def record_test(self, connector_id: str, result: BaseModel, *, secret_ready: bool) -> None:
        payload = result.model_dump(mode="json")
        manifest = self.load(connector_id)
        readiness = (
            "NOT_REQUIRED" if not manifest.secret_references else ("READY" if secret_ready else "MISSING")
        )
        with self.connection:
            self.connection.execute(
                """UPDATE connectors SET last_test_json=?,provider_health=?,secret_readiness=?,
                   updated_at=? WHERE id=?""",
                (
                    _json(payload),
                    payload["status"],
                    readiness,
                    datetime.now(UTC).isoformat(),
                    connector_id,
                ),
            )

    def record_sync(self, connector_id: str, result: BaseModel) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE connectors SET last_sync_json=?,updated_at=? WHERE id=?",
                (
                    _json(result.model_dump(mode="json")),
                    datetime.now(UTC).isoformat(),
                    connector_id,
                ),
            )

    def cursor(self, connector_id: str, resource_id: str) -> str | None:
        row = self.connection.execute(
            "SELECT cursor FROM connector_cursors WHERE connector_id=? AND resource_id=?",
            (connector_id, resource_id),
        ).fetchone()
        return str(row["cursor"]) if row and row["cursor"] is not None else None

    def close(self) -> None:
        self.connection.close()
