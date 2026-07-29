from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


def _slug(value: str) -> str:
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value).lower()
    return re.sub(r"[^a-z0-9]+", "-", words).strip("-")


@dataclass(frozen=True)
class OpenAPIImportResult:
    connector_path: Path
    manifest_path: Path
    operations: int
    unresolved_mappings: tuple[str, ...]


class OpenAPIImporter:
    def __init__(self, output_root: Path | str, *, client: httpx.Client | None = None) -> None:
        self.output_root = Path(output_root)
        self.client = client

    def load(self, path_or_url: Path | str) -> dict[str, Any]:
        source = str(path_or_url)
        if source.startswith(("https://", "http://")):
            if not source.startswith("https://"):
                raise ValueError("OpenAPI URL imports require HTTPS")
            if self.client is not None:
                response = self.client.get(source)
                response.raise_for_status()
                document = response.json()
            else:
                with httpx.Client(timeout=10.0, follow_redirects=False) as client:
                    response = client.get(source)
                    response.raise_for_status()
                    document = response.json()
        else:
            document = json.loads(Path(path_or_url).read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError("OpenAPI document must be an object")
        return document

    def import_source(
        self, path_or_url: Path | str, *, connector_id: str | None = None
    ) -> OpenAPIImportResult:
        return self.import_document(self.load(path_or_url), connector_id=connector_id)

    def import_document(
        self,
        document: dict[str, Any],
        *,
        connector_id: str | None = None,
    ) -> OpenAPIImportResult:
        version = str(document.get("openapi", ""))
        if not version.startswith(("3.0.", "3.1.")):
            raise ValueError("only OpenAPI 3.0 and 3.1 are supported")
        info = document.get("info")
        if not isinstance(info, dict):
            raise ValueError("OpenAPI info is required")
        identifier = _slug(connector_id or str(info.get("title", "connector")))
        if len(identifier) < 2:
            raise ValueError("connector ID is invalid")
        servers = document.get("servers") or []
        base_url = str(servers[0].get("url")) if servers and isinstance(servers[0], dict) else None
        host = urlparse(base_url).hostname if base_url else None
        resources: list[dict[str, Any]] = []
        read_operations: list[str] = []
        write_operations: list[str] = []
        unresolved: list[str] = []
        schemas: dict[str, Any] = {}
        pagination_type = "none"
        for path, path_item in sorted(dict(document.get("paths", {})).items()):
            if not isinstance(path_item, dict):
                continue
            for method in ("get", "post", "put", "patch", "delete"):
                operation = path_item.get(method)
                if not isinstance(operation, dict):
                    continue
                operation_id = _slug(str(operation.get("operationId") or f"{method}-{path}"))
                response_schema: dict[str, Any] = {}
                for response in dict(operation.get("responses", {})).values():
                    if not isinstance(response, dict):
                        continue
                    content = response.get("content", {})
                    if isinstance(content, dict):
                        media = content.get("application/json", {})
                        if isinstance(media, dict) and isinstance(media.get("schema"), dict):
                            response_schema = media["schema"]
                            break
                schemas[operation_id] = response_schema or {"type": "object"}
                parameters = list(operation.get("parameters", []))
                names = {
                    str(item.get("name", "")).lower()
                    for item in parameters
                    if isinstance(item, dict) and item.get("in") == "query"
                }
                if {"cursor", "after"} & names:
                    pagination_type = "cursor"
                elif {"page", "page_number", "offset"} & names and pagination_type == "none":
                    pagination_type = "page_number"
                resources.append(
                    {
                        "id": operation_id,
                        "path": path,
                        "method": method.upper(),
                        "response_items_path": "items",
                    }
                )
                if method == "get":
                    read_operations.append(operation_id)
                else:
                    write_operations.append(operation_id)
                unresolved.append(operation_id)
        security_schemes = dict(document.get("components", {})).get("securitySchemes", {})
        auth_inventory = sorted(dict(security_schemes)) if isinstance(security_schemes, dict) else []
        connector_path = self.output_root / "connectors" / identifier
        schemas_path = connector_path / "schemas"
        fixtures_path = connector_path / "fixtures"
        tests_path = connector_path / "tests"
        for directory in (schemas_path, fixtures_path, tests_path):
            directory.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": 1,
            "id": identifier,
            "display_name": str(info.get("title") or identifier),
            "version": str(info.get("version") or "0.0.0"),
            "protocol": "rest",
            "base_url": base_url,
            "authentication": {"type": "none"},
            "resources": resources,
            "pagination": {"type": pagination_type},
            "allowed_hosts": [host] if host else [],
            "read_operations": read_operations,
            "write_operations": write_operations,
            "risk_class": "controlled_write" if write_operations else "read_only",
            "activation_state": "INACTIVE_REVIEW_REQUIRED",
            "review_required": True,
            "auth_scheme_inventory": auth_inventory,
        }
        manifest_path = connector_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (connector_path / "openapi-source.json").write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        for operation_id, schema in schemas.items():
            (schemas_path / f"{operation_id}.json").write_text(
                json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        mapping = {
            "review_required": True,
            "unresolved_operations": unresolved,
            "note": "Map provider fields to canonical records before activation.",
        }
        (connector_path / "mapping.todo.json").write_text(
            json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (fixtures_path / ".gitkeep").touch()
        (tests_path / ".gitkeep").touch()
        return OpenAPIImportResult(
            connector_path=connector_path,
            manifest_path=manifest_path,
            operations=len(resources),
            unresolved_mappings=tuple(unresolved),
        )
