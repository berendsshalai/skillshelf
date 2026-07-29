from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .contracts import ConnectorManifest
from .openapi import OpenAPIImporter
from .registry import ConnectorRecord, ConnectorRegistry


class ConnectorOnboardingService:
    """Shared service used by interactive and manifest-driven onboarding."""

    def __init__(self, registry: ConnectorRegistry, *, importer: OpenAPIImporter | None = None) -> None:
        self.registry = registry
        self.importer = importer

    def add_manifest(self, path: Path | str) -> ConnectorRecord:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("connector manifest must be an object")
        payload.pop("activation_state", None)
        payload.pop("review_required", None)
        payload.pop("auth_scheme_inventory", None)
        return self.registry.add(ConnectorManifest.model_validate(payload))

    def interactive(self, prompt: Callable[[str], str]) -> ConnectorRecord:
        display_name = prompt("Display name")
        connector_id = prompt("Connector ID")
        base_url = prompt("Base URL")
        allowed_hosts = [value.strip() for value in prompt("Allowed hosts (comma separated)").split(",")]
        auth_type = prompt("Authentication type") or "none"
        secret_reference = prompt("Primary secret reference") or None
        test_operation = prompt("Test/read operation ID") or "read"
        operation_path = prompt("Read operation path") or "/"
        manifest = ConnectorManifest.model_validate(
            {
                "id": connector_id,
                "display_name": display_name,
                "version": "1.0.0",
                "protocol": "rest",
                "base_url": base_url,
                "authentication": {"type": auth_type, "secret_reference": secret_reference},
                "resources": [{"id": test_operation, "path": operation_path}],
                "secret_references": [secret_reference] if secret_reference else [],
                "allowed_hosts": allowed_hosts,
                "read_operations": [test_operation],
            }
        )
        return self.registry.add(manifest)
