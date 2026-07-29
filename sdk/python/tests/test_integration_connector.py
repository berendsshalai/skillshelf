from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from skillshelf_agents.connectors import ConnectorManifest, EnvironmentSecretStore, RESTConnector


def test_manifest_secret_pagination_incremental_etag_and_redaction(monkeypatch):
    calls: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            calls.append({"query": query, "key": self.headers.get("X-API-Key")})
            if len(calls) == 1:
                self.send_response(429)
                self.send_header("Retry-After", "0")
                self.end_headers()
                return
            if self.headers.get("If-None-Match") == '"stock-v1"':
                self.send_response(304)
                self.end_headers()
                return
            page = int(query.get("page", ["1"])[0])
            items = [{"id": f"stock-{page}"}] if page <= 2 else []
            body = json.dumps({"items": items}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("ETag", '"stock-v1"')
            self.send_header("X-RateLimit-Remaining", "8")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("SKILLSHELF_TEST_KEY", "super-secret")
    try:
        manifest = ConnectorManifest.model_validate(
            {
                "schema_version": 1,
                "id": "local-stock",
                "display_name": "Local stock",
                "version": "1.0.0",
                "protocol": "rest",
                "base_url": f"http://127.0.0.1:{server.server_port}/",
                "authentication": {
                    "type": "api_key_header",
                    "secret_reference": "SKILLSHELF_TEST_KEY",
                    "parameter_name": "X-API-Key",
                },
                "resources": [
                    {
                        "id": "stock",
                        "path": "/stock",
                        "updated_since_parameter": "updated_since",
                    }
                ],
                "pagination": {"type": "page_number", "maximum_pages": 5},
                "secret_references": ["SKILLSHELF_TEST_KEY"],
                "allowed_hosts": ["127.0.0.1"],
                "read_operations": ["stock"],
            }
        )
        connector = RESTConnector(
            manifest,
            EnvironmentSecretStore(),
            allow_private_hosts=True,
            allow_insecure_http=True,
            sleeper=lambda _delay: None,
        )
        first = connector.read("stock", updated_since="2026-07-01T00:00:00Z")
        second = connector.read("stock")
        assert [item["id"] for item in first.items] == ["stock-1", "stock-2"]
        assert first.pages == 3
        assert second.not_modified
        assert first.rate_limit_headers == {"x-ratelimit-remaining": "8"}
        assert calls[0]["query"]["updated_since"] == ["2026-07-01T00:00:00Z"]
        assert len(calls) == 5  # one throttled attempt, three pages, then one 304
        assert all(call["key"] == "super-secret" for call in calls)
        assert "super-secret" not in json.dumps(connector.request_log)
        connector.close()
    finally:
        server.shutdown()
        thread.join()
