from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from .registry import ConnectorRegistry
from .rest import RESTConnector, RESTResult
from .secrets import SecretStore


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


class ConnectorTestResult(BaseModel):
    connector_id: str
    status: Literal["PASS", "DEGRADED", "FAIL"]
    network: Literal["LIVE", "OFFLINE_FIXTURE"]
    status_code: int
    pages: int
    latency_ms: float
    rate_limit_headers: dict[str, str]
    response_digest: str
    schema_valid: bool
    pagination_valid: bool
    tested_at: datetime
    error_code: str | None = None


class ConnectorSyncReport(BaseModel):
    connector_id: str
    resource_id: str
    raw_records: int
    canonical_records: int
    quarantined_records: int
    pages: int
    committed_cursor: str | None
    dry_run: bool
    started_at: datetime
    completed_at: datetime


class ConnectorService:
    def __init__(
        self,
        registry: ConnectorRegistry,
        secret_store: SecretStore,
        *,
        connector_factory: type[RESTConnector] = RESTConnector,
    ) -> None:
        self.registry = registry
        self.secret_store = secret_store
        self.connector_factory = connector_factory

    def _secrets_ready(self, connector_id: str) -> bool:
        manifest = self.registry.load(connector_id)
        try:
            for reference in manifest.secret_references:
                self.secret_store.get(reference)
        except (KeyError, ValueError):
            return False
        return True

    @staticmethod
    def _fixture_read(
        fixture: dict[str, Any], maximum_pages: int | None = None
    ) -> tuple[list[dict[str, Any]], int, dict[str, str], str | None]:
        pages = fixture.get("pages")
        if not isinstance(pages, list) or not pages:
            raise ValueError("offline fixture requires a non-empty pages array")
        selected = pages[:maximum_pages] if maximum_pages else pages
        items: list[dict[str, Any]] = []
        headers: dict[str, str] = {}
        cursor: str | None = None
        for page in selected:
            if not isinstance(page, dict) or int(page.get("status", 0)) >= 400:
                raise ValueError("offline fixture contains a failed response")
            body = page.get("body")
            if not isinstance(body, dict) or not isinstance(body.get("items"), list):
                raise ValueError("offline fixture response schema is invalid")
            if any(not isinstance(item, dict) for item in body["items"]):
                raise ValueError("offline fixture items must be objects")
            items.extend(body["items"])
            headers.update({str(key): str(value) for key, value in dict(page.get("headers", {})).items()})
            cursor_value = body.get("next_cursor")
            if cursor_value:
                cursor = str(cursor_value)
        return items, len(selected), headers, cursor

    def test(
        self,
        connector_id: str,
        *,
        operation_id: str | None = None,
        offline_fixture: dict[str, Any] | None = None,
        allow_private_hosts: bool = False,
        allow_insecure_http: bool = False,
    ) -> ConnectorTestResult:
        manifest = self.registry.load(connector_id)
        resource_id = operation_id or manifest.read_operations[0]
        started = time.perf_counter()
        secret_ready = self._secrets_ready(connector_id)
        try:
            if not secret_ready:
                raise KeyError("required secret is not configured")
            if offline_fixture is not None:
                items, pages, headers, _cursor = self._fixture_read(offline_fixture)
                status_code = 200
                network: Literal["LIVE", "OFFLINE_FIXTURE"] = "OFFLINE_FIXTURE"
            else:
                connector = self.connector_factory(
                    manifest,
                    self.secret_store,
                    allow_private_hosts=allow_private_hosts,
                    allow_insecure_http=allow_insecure_http,
                )
                try:
                    response: RESTResult = connector.read(resource_id)
                finally:
                    connector.close()
                items = list(response.items)
                pages = response.pages
                headers = response.rate_limit_headers
                status_code = response.status_code
                network = "LIVE"
            pagination_valid = manifest.pagination is None or pages >= 1
            result = ConnectorTestResult(
                connector_id=connector_id,
                status="PASS" if pagination_valid else "DEGRADED",
                network=network,
                status_code=status_code,
                pages=pages,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                rate_limit_headers={
                    key: value
                    for key, value in headers.items()
                    if "rate" in key.lower() or key.lower() == "retry-after"
                },
                response_digest=_digest(items),
                schema_valid=True,
                pagination_valid=pagination_valid,
                tested_at=datetime.now(UTC),
            )
        except (IndexError, KeyError, ValueError, RuntimeError, httpx.HTTPError) as error:
            result = ConnectorTestResult(
                connector_id=connector_id,
                status="FAIL",
                network="OFFLINE_FIXTURE" if offline_fixture is not None else "LIVE",
                status_code=0,
                pages=0,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                rate_limit_headers={},
                response_digest=_digest({"error": type(error).__name__}),
                schema_valid=False,
                pagination_valid=False,
                tested_at=datetime.now(UTC),
                error_code=type(error).__name__,
            )
        self.registry.record_test(connector_id, result, secret_ready=secret_ready)
        return result

    def sync(
        self,
        connector_id: str,
        *,
        resource_id: str,
        tenant_id: str,
        since: str | None = None,
        maximum_pages: int | None = None,
        dry_run: bool = False,
        fixture: dict[str, Any] | None = None,
        canonical_required_fields: tuple[str, ...] = ("id",),
        now: datetime | None = None,
    ) -> ConnectorSyncReport:
        del tenant_id  # Tenant separation belongs to canonical mapping configuration.
        started = now or datetime.now(UTC)
        manifest = self.registry.load(connector_id)
        manifest.resource(resource_id)
        previous_cursor = since if since is not None else self.registry.cursor(connector_id, resource_id)
        if fixture is not None:
            items, pages, _headers, next_cursor = self._fixture_read(fixture, maximum_pages)
        else:
            connector = self.connector_factory(manifest, self.secret_store)
            try:
                response = connector.read(resource_id, updated_since=previous_cursor)
            finally:
                connector.close()
            items, pages, next_cursor = list(response.items), response.pages, previous_cursor
        connection = self.registry.connection
        raw = canonical = quarantined = 0
        try:
            connection.execute("BEGIN")
            for index, item in enumerate(items):
                external_id = str(item.get("id") or f"missing-{index}")
                content_hash = _digest(item)
                inserted = connection.execute(
                    """INSERT OR IGNORE INTO connector_raw_records
                       (connector_id,resource_id,external_id,content_hash,payload_json,observed_at)
                       VALUES(?,?,?,?,?,?)""",
                    (
                        connector_id,
                        resource_id,
                        external_id,
                        content_hash,
                        json.dumps(item, sort_keys=True),
                        started.isoformat(),
                    ),
                ).rowcount
                raw += int(inserted)
                missing = [field for field in canonical_required_fields if item.get(field) in (None, "")]
                if missing:
                    connection.execute(
                        """INSERT INTO connector_quarantines
                           (connector_id,resource_id,external_id,reason,payload_hash,observed_at)
                           VALUES(?,?,?,?,?,?)""",
                        (
                            connector_id,
                            resource_id,
                            external_id,
                            f"missing:{','.join(missing)}",
                            content_hash,
                            started.isoformat(),
                        ),
                    )
                    quarantined += 1
                else:
                    canonical += int(
                        connection.execute(
                            """INSERT OR IGNORE INTO connector_canonical_records
                               VALUES(?,?,?,?,?,?)""",
                            (
                                connector_id,
                                resource_id,
                                external_id,
                                json.dumps(item, sort_keys=True),
                                content_hash,
                                started.isoformat(),
                            ),
                        ).rowcount
                    )
            committed_cursor = next_cursor or previous_cursor
            connection.execute(
                """INSERT INTO connector_cursors VALUES(?,?,?,?)
                   ON CONFLICT(connector_id,resource_id)
                   DO UPDATE SET cursor=excluded.cursor,updated_at=excluded.updated_at""",
                (connector_id, resource_id, committed_cursor, started.isoformat()),
            )
            if dry_run:
                connection.rollback()
                committed_cursor = previous_cursor
            else:
                connection.commit()
        except Exception:
            connection.rollback()
            raise
        report = ConnectorSyncReport(
            connector_id=connector_id,
            resource_id=resource_id,
            raw_records=raw,
            canonical_records=canonical,
            quarantined_records=quarantined,
            pages=pages,
            committed_cursor=committed_cursor,
            dry_run=dry_run,
            started_at=started,
            completed_at=datetime.now(UTC),
        )
        if not dry_run:
            self.registry.record_sync(connector_id, report)
        return report
