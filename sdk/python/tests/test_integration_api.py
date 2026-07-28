from fastapi.testclient import TestClient

from skillshelf_agents.api import create_app


def test_local_control_plane_health_connectors_webhooks_and_suggestions(tmp_path):
    client = TestClient(create_app(tmp_path))
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}

    manifest = {
        "schema_version": 1,
        "id": "stock-api",
        "display_name": "Stock API",
        "version": "1.0.0",
        "protocol": "rest",
        "base_url": "https://stock.example.test",
        "authentication": {"type": "none"},
        "resources": [{"id": "inventory", "path": "/inventory"}],
        "allowed_hosts": ["stock.example.test"],
        "read_operations": ["inventory"],
        "risk_class": "read_only",
    }
    created = client.post("/connectors", json=manifest)
    assert created.status_code == 201
    assert client.get("/connectors").json()[0]["id"] == "stock-api"
    assert client.post("/connectors/stock-api/test").json()["network"] == "not-invoked"
    assert client.post("/connectors/stock-api/sync").status_code == 409

    first = client.post("/webhooks/stock-api", content=b'{"event_id":"evt-1"}')
    second = client.post("/webhooks/stock-api", content=b'{"event_id":"evt-1"}')
    assert first.status_code == second.status_code == 202
    assert first.json()["event_id"] == second.json()["event_id"]
    assert client.get("/workflows").json()[0]["id"] == "stock-to-offer-v1"
    codes = {item["code"] for item in client.get("/suggestions").json()}
    assert "connect-stock" not in codes
    assert "configure-pricing" in codes
