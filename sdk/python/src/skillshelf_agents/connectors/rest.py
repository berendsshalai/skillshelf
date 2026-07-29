from __future__ import annotations

import base64
import ipaddress
import random
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import httpx

from .contracts import ConnectorManifest, ResourceDefinition
from .secrets import SecretStore


@dataclass(frozen=True)
class RESTResult:
    items: tuple[dict[str, Any], ...]
    status_code: int
    pages: int
    etag: str | None
    not_modified: bool
    request_count: int
    rate_limit_headers: dict[str, str] = field(default_factory=dict)


class CircuitOpenError(RuntimeError):
    pass


class RESTConnector:
    def __init__(
        self,
        manifest: ConnectorManifest,
        secret_store: SecretStore,
        *,
        client: httpx.Client | None = None,
        allow_private_hosts: bool = False,
        allow_insecure_http: bool = False,
        sleeper: Callable[[float], None] = time.sleep,
        random_source: random.Random | None = None,
    ) -> None:
        if manifest.protocol != "rest":
            raise ValueError("RESTConnector requires protocol=rest")
        self.manifest = manifest
        self.secret_store = secret_store
        self.client = client or httpx.Client(timeout=10.0, follow_redirects=False)
        self._owns_client = client is None
        self.allow_private_hosts = allow_private_hosts
        self.allow_insecure_http = allow_insecure_http
        self.sleeper = sleeper
        self.random: random.Random = random_source or random.Random()
        self._etags: dict[str, str] = {}
        self._consecutive_failures = 0
        self._circuit_opened_at: float | None = None
        self.request_log: list[dict[str, Any]] = []

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ({"https", "http"} if self.allow_insecure_http else {"https"}):
            raise ValueError("connector URL violates HTTPS policy")
        if not parsed.hostname or parsed.hostname not in self.manifest.allowed_hosts:
            raise ValueError("connector host is not allowed")
        if parsed.username or parsed.password:
            raise ValueError("userinfo credentials are forbidden in connector URLs")
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not self.allow_private_hosts and (
                ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            ):
                raise ValueError("connector host resolves to a private or reserved address")

    def _auth(self) -> tuple[dict[str, str], dict[str, str]]:
        definition = self.manifest.authentication
        headers: dict[str, str] = {"User-Agent": "SkillShelf/0.3 connector"}
        query: dict[str, str] = {}
        if definition.type == "none":
            return headers, query
        primary = self.secret_store.get(definition.secret_reference or "")
        if definition.type == "api_key_header":
            headers[definition.parameter_name or "X-API-Key"] = primary
        elif definition.type == "api_key_query":
            query[definition.parameter_name or "api_key"] = primary
        elif definition.type == "bearer":
            headers["Authorization"] = f"Bearer {primary}"
        elif definition.type == "basic":
            password = self.secret_store.get(definition.secondary_secret_reference or "")
            token = base64.b64encode(f"{primary}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"
        else:
            raise NotImplementedError(f"{definition.type} token acquisition requires an OAuth adapter")
        return headers, query

    @staticmethod
    def _dig(payload: Any, dotted_path: str) -> Any:
        value = payload
        for part in dotted_path.split("."):
            if not part:
                continue
            if not isinstance(value, dict) or part not in value:
                raise ValueError(f"response schema drift at {dotted_path}")
            value = value[part]
        return value

    def _retry_delay(self, response: httpx.Response | None, attempt: int) -> float:
        if response is not None:
            value = response.headers.get(self.manifest.rate_limit.retry_after_header)
            if value:
                try:
                    return float(min(float(value), self.manifest.retry_policy.maximum_delay_seconds))
                except ValueError:
                    try:
                        seconds = float(
                            (parsedate_to_datetime(value) - datetime.now().astimezone()).total_seconds()
                        )
                        return float(max(0.0, seconds))
                    except (TypeError, ValueError):
                        pass
        base = self.manifest.retry_policy.base_delay_seconds * (2 ** (attempt - 1))
        jitter = self.random.uniform(0, max(base * 0.25, 0.0001))
        return float(min(base + jitter, self.manifest.retry_policy.maximum_delay_seconds))

    def _request(
        self,
        resource: ResourceDefinition,
        url: str,
        params: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
        policy = self.manifest.retry_policy
        if self._circuit_opened_at is not None:
            if time.monotonic() - self._circuit_opened_at < policy.circuit_reset_seconds:
                raise CircuitOpenError("connector circuit is open")
            self._circuit_opened_at = None
            self._consecutive_failures = 0
        response: httpx.Response | None = None
        for attempt in range(1, policy.maximum_attempts + 1):
            try:
                response = self.client.request(resource.method, url, params=params, headers=headers)
                if response.status_code not in {429, 500, 502, 503, 504}:
                    self._consecutive_failures = 0
                    return response
            except (httpx.TimeoutException, httpx.NetworkError):
                response = None
            self._consecutive_failures += 1
            if self._consecutive_failures >= policy.circuit_failure_threshold:
                self._circuit_opened_at = time.monotonic()
            if attempt < policy.maximum_attempts:
                self.sleeper(self._retry_delay(response, attempt))
        if response is not None:
            response.raise_for_status()
        raise httpx.ConnectError("connector request failed after retries")

    def read(
        self,
        resource_id: str,
        *,
        query: dict[str, Any] | None = None,
        updated_since: str | None = None,
    ) -> RESTResult:
        if resource_id not in self.manifest.read_operations:
            raise PermissionError(f"resource is not approved for reads: {resource_id}")
        resource = self.manifest.resource(resource_id)
        url = urljoin(str(self.manifest.base_url), resource.path.lstrip("/"))
        self._validate_url(url)
        headers, auth_query = self._auth()
        params = {**auth_query, **(query or {})}
        if updated_since:
            if not resource.updated_since_parameter:
                raise ValueError("resource does not support updated_since")
            params[resource.updated_since_parameter] = updated_since
        if etag := self._etags.get(resource_id):
            headers["If-None-Match"] = etag
        pagination = self.manifest.pagination
        page = pagination.start_page if pagination else 1
        cursor: str | None = None
        next_url: str | None = url
        items: list[dict[str, Any]] = []
        request_count = 0
        pages = 0
        status_code = 0
        response_etag: str | None = None
        rate_limit_headers: dict[str, str] = {}
        while next_url:
            request_params = dict(params)
            if pagination and pagination.type == "page_number":
                request_params[pagination.page_parameter] = page
            elif pagination and pagination.type == "cursor" and cursor:
                request_params[pagination.cursor_parameter] = cursor
            response = self._request(resource, next_url, request_params, headers)
            request_count += 1
            status_code = response.status_code
            rate_limit_headers.update(
                {
                    key: value
                    for key, value in response.headers.items()
                    if "rate" in key.lower() or key.lower() == "retry-after"
                }
            )
            self.request_log.append(
                {
                    "method": resource.method,
                    "url": next_url,
                    "status": status_code,
                    "headers": sorted(key for key in headers if key.lower() != "authorization"),
                }
            )
            if status_code == 304:
                return RESTResult(
                    (),
                    status_code,
                    pages,
                    self._etags.get(resource_id),
                    True,
                    request_count,
                    rate_limit_headers,
                )
            response.raise_for_status()
            content = response.content
            if len(content) > resource.maximum_payload_bytes:
                raise ValueError("connector response exceeds maximum payload size")
            payload = response.json()
            page_items = self._dig(payload, resource.response_items_path)
            if not isinstance(page_items, list) or any(not isinstance(item, dict) for item in page_items):
                raise ValueError("response schema drift: items must be a list of objects")
            items.extend(page_items)
            pages += 1
            response_etag = response.headers.get("ETag") or response_etag
            if not pagination or pagination.type == "none":
                next_url = None
            elif pages >= pagination.maximum_pages:
                raise ValueError("pagination exceeded maximum pages")
            elif pagination.type == "page_number":
                next_url = url if page_items else None
                page += 1
            elif pagination.type == "cursor":
                cursor_value = self._dig(payload, pagination.next_cursor_path)
                cursor = str(cursor_value) if cursor_value else None
                next_url = url if cursor else None
            else:
                link = response.links.get("next")
                next_url = str(link["url"]) if link else None
                if next_url:
                    self._validate_url(next_url)
        if response_etag:
            self._etags[resource_id] = response_etag
        return RESTResult(
            tuple(items),
            status_code,
            pages,
            response_etag,
            False,
            request_count,
            rate_limit_headers,
        )
