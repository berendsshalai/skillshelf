from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status

from skillshelf_agents.connectors import ConnectorManifest
from skillshelf_agents.suggestions.engine import CapabilityState, suggest_capabilities


def create_app(state_root: Path | str = ".skillshelf") -> FastAPI:
    root = Path(state_root).resolve()
    connectors = root / "connectors"
    connectors.mkdir(parents=True, exist_ok=True)
    database = root / "operations.sqlite"
    app = FastAPI(title="SkillShelf control plane", version="0.3.0")

    def workflow_rows() -> list[dict[str, Any]]:
        if not database.exists():
            return []
        with sqlite3.connect(database) as connection:
            connection.row_factory = sqlite3.Row
            try:
                return [
                    dict(row)
                    for row in connection.execute(
                        "SELECT id,tenant_id,workflow_id,state,created_at,updated_at FROM workflow_runs ORDER BY created_at DESC"
                    )
                ]
            except sqlite3.OperationalError:
                return []

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        try:
            root.mkdir(parents=True, exist_ok=True)
            probe = root / ".ready"
            probe.touch(exist_ok=True)
            probe.unlink()
        except OSError as error:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
        return {"status": "ready"}

    @app.get("/connectors")
    def list_connectors() -> list[dict[str, Any]]:
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(connectors.glob("*.json"))]

    @app.post("/connectors", status_code=status.HTTP_201_CREATED)
    def add_connector(manifest: ConnectorManifest) -> dict[str, Any]:
        destination = connectors / f"{manifest.id}.json"
        if destination.exists():
            raise HTTPException(status.HTTP_409_CONFLICT, "connector already exists")
        destination.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return manifest.model_dump(mode="json")

    @app.post("/connectors/{connector_id}/test")
    def test_connector(connector_id: str) -> dict[str, str]:
        path = connectors / f"{connector_id}.json"
        if not path.exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "connector not found")
        manifest = ConnectorManifest.model_validate_json(path.read_text(encoding="utf-8"))
        return {"id": manifest.id, "status": "validated", "network": "not-invoked"}

    @app.post("/connectors/{connector_id}/sync")
    def sync_connector(connector_id: str) -> dict[str, str]:
        if not (connectors / f"{connector_id}.json").exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "connector not found")
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "sync requires an explicitly configured operation and secret references",
        )

    @app.get("/workflows")
    def workflows() -> list[dict[str, str]]:
        return [{"id": "stock-to-offer-v1", "storage": str(database)}]

    @app.post("/workflows/{workflow_id}/run")
    def run_workflow(workflow_id: str) -> dict[str, str]:
        if workflow_id != "stock-to-offer-v1":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "workflow not found")
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "use the typed stock-to-offer input with configured consent, delivery and channel services",
        )

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        matches = [row for row in workflow_rows() if row["id"] == run_id]
        if not matches:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
        return matches[0]

    @app.post("/runs/{run_id}/approve")
    def approve_run(run_id: str) -> dict[str, str]:
        raise HTTPException(status.HTTP_409_CONFLICT, f"run {run_id} has no API approval request")

    @app.post("/runs/{run_id}/resume")
    def resume_run(run_id: str) -> dict[str, str]:
        raise HTTPException(status.HTTP_409_CONFLICT, f"run {run_id} is not resumable through this endpoint")

    @app.post("/runs/{run_id}/cancel")
    def cancel_run(run_id: str) -> dict[str, str]:
        if not database.exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
        with sqlite3.connect(database) as connection:
            cursor = connection.execute(
                "UPDATE workflow_runs SET state='CANCELLED' WHERE id=? AND state NOT IN ('COMPLETED','FAILED','CANCELLED')",
                (run_id,),
            )
        if cursor.rowcount != 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "run cannot be cancelled")
        return {"id": run_id, "state": "CANCELLED"}

    @app.post("/webhooks/{connector_id}", status_code=status.HTTP_202_ACCEPTED)
    async def webhook(connector_id: str, request: Request) -> dict[str, str]:
        if not (connectors / f"{connector_id}.json").exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "connector not found")
        payload = await request.body()
        inbox = root / "webhooks" / connector_id
        inbox.mkdir(parents=True, exist_ok=True)
        import hashlib

        event_id = hashlib.sha256(payload).hexdigest()
        path = inbox / f"{event_id}.json"
        if not path.exists():
            path.write_bytes(payload)
        return {"event_id": event_id, "status": "accepted"}

    @app.get("/usage")
    def usage() -> dict[str, int]:
        rows = workflow_rows()
        return {"workflow_runs": len(rows)}

    @app.get("/suggestions")
    def suggestions() -> list[dict[str, Any]]:
        state = CapabilityState(
            has_stock_source=any(connectors.glob("*.json")),
            has_pricing_rule=False,
            has_delivery_provider=False,
            has_customer_consent=False,
            has_message_channel=False,
        )
        return [item.model_dump() for item in suggest_capabilities(state)]

    return app
