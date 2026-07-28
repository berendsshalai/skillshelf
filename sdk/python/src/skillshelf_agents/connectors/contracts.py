from __future__ import annotations

from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator


class AuthenticationDefinition(BaseModel):
    type: Literal[
        "none",
        "api_key_header",
        "api_key_query",
        "bearer",
        "basic",
        "oauth2_client_credentials",
        "oauth2_authorization_code",
    ] = "none"
    secret_reference: str | None = None
    secondary_secret_reference: str | None = None
    parameter_name: str | None = None
    token_url: AnyHttpUrl | None = None

    @model_validator(mode="after")
    def validate_secret_reference(self) -> "AuthenticationDefinition":
        if self.type != "none" and not self.secret_reference:
            raise ValueError(f"{self.type} requires a secret reference")
        if self.type == "basic" and not self.secondary_secret_reference:
            raise ValueError("basic authentication requires username and password references")
        if self.type.startswith("oauth2_") and not self.token_url:
            raise ValueError("OAuth authentication requires token_url")
        return self


class ResourceDefinition(BaseModel):
    id: str
    path: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    response_items_path: str = "items"
    updated_since_parameter: str | None = None
    maximum_payload_bytes: int = Field(default=1_048_576, ge=1, le=20_971_520)


class PaginationDefinition(BaseModel):
    type: Literal["none", "page_number", "cursor", "link_header"] = "none"
    page_parameter: str = "page"
    start_page: int = 1
    cursor_parameter: str = "cursor"
    next_cursor_path: str = "next_cursor"
    maximum_pages: int = Field(default=100, ge=1, le=10_000)


class RateLimitDefinition(BaseModel):
    requests_per_second: float = Field(default=10.0, gt=0, le=1000)
    retry_after_header: str = "Retry-After"


class RetryPolicy(BaseModel):
    maximum_attempts: int = Field(default=3, ge=1, le=10)
    base_delay_seconds: float = Field(default=0.01, ge=0, le=60)
    maximum_delay_seconds: float = Field(default=2.0, ge=0, le=300)
    circuit_failure_threshold: int = Field(default=3, ge=1, le=100)
    circuit_reset_seconds: float = Field(default=30.0, ge=0, le=3600)


class WebhookDefinition(BaseModel):
    event_id_path: str = "event_id"
    event_type_path: str = "type"
    signature_header: str | None = None
    secret_reference: str | None = None


class ConnectorManifest(BaseModel):
    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    display_name: str
    version: str
    protocol: Literal["rest", "graphql", "webhook", "file", "database"]
    base_url: AnyHttpUrl | None = None
    authentication: AuthenticationDefinition = Field(default_factory=AuthenticationDefinition)
    resources: list[ResourceDefinition]
    pagination: PaginationDefinition | None = None
    rate_limit: RateLimitDefinition = Field(default_factory=RateLimitDefinition)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    webhook: WebhookDefinition | None = None
    secret_references: list[str] = Field(default_factory=list)
    allowed_hosts: list[str]
    read_operations: list[str]
    write_operations: list[str] = Field(default_factory=list)
    risk_class: Literal["read_only", "controlled_write", "high_impact"] = "read_only"

    @model_validator(mode="after")
    def validate_manifest(self) -> "ConnectorManifest":
        if self.protocol in {"rest", "graphql"} and self.base_url is None:
            raise ValueError("network connector requires base_url")
        if self.base_url and self.base_url.host not in self.allowed_hosts:
            raise ValueError("base_url host must be explicitly allowed")
        operation_ids = {resource.id for resource in self.resources}
        if not set(self.read_operations + self.write_operations) <= operation_ids:
            raise ValueError("operations must reference declared resources")
        if self.write_operations and self.risk_class == "read_only":
            raise ValueError("read_only connector cannot declare writes")
        declared = set(self.secret_references)
        for reference in (
            self.authentication.secret_reference,
            self.authentication.secondary_secret_reference,
            self.webhook.secret_reference if self.webhook else None,
        ):
            if reference and reference not in declared:
                raise ValueError(f"secret reference {reference!r} is not declared")
        return self

    def resource(self, resource_id: str) -> ResourceDefinition:
        for resource in self.resources:
            if resource.id == resource_id:
                return resource
        raise KeyError(resource_id)
