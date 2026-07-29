from __future__ import annotations

import hashlib
import hmac
import json
import base64
from datetime import UTC, datetime
from pathlib import Path

from skillshelf_agents.communications.providers import (
    MetaInstagramAdapter,
    MetaWhatsAppAdapter,
    IdempotentWebhookReconciler,
    ProviderSendError,
    ProviderRequest,
    ProviderResponse,
    SMTPAdapter,
    TwilioSMSAdapter,
    TwilioVoiceAdapter,
    verify_meta_signature,
    verify_twilio_signature,
)
from skillshelf_agents.connectors import ConnectorManifest
from skillshelf_agents.connectors.openapi import OpenAPIImporter
from skillshelf_agents.connectors.registry import ConnectorRegistry
from skillshelf_agents.connectors.service import ConnectorService
from skillshelf_agents.connectors.secrets import EnvironmentSecretStore
from skillshelf_agents.workflows import (
    DurableWorkflowEngine,
    RetryPolicy,
    WorkflowDefinition,
    WorkflowRegistry,
    WorkflowState,
    WorkflowStepDefinition,
    WaitForExternalEvent,
    stock_to_offer_definition,
)


def _manifest() -> ConnectorManifest:
    return ConnectorManifest.model_validate(
        {
            "schema_version": 1,
            "id": "fixture-stock",
            "display_name": "Fixture stock",
            "version": "1.0.0",
            "protocol": "rest",
            "base_url": "https://stock.example.test/",
            "resources": [{"id": "stock", "path": "/stock", "updated_since_parameter": "since"}],
            "pagination": {"type": "cursor", "next_cursor_path": "next_cursor"},
            "allowed_hosts": ["stock.example.test"],
            "read_operations": ["stock"],
        }
    )


def test_connector_registry_offline_test_and_transactional_sync(tmp_path: Path) -> None:
    registry = ConnectorRegistry(tmp_path / "connectors.sqlite")
    registry.add(_manifest())
    assert registry.inspect("fixture-stock").activation_state == "INACTIVE"

    service = ConnectorService(registry, EnvironmentSecretStore({}))
    fixture = {
        "pages": [
            {
                "status": 200,
                "headers": {"X-RateLimit-Remaining": "9"},
                "body": {
                    "items": [
                        {"id": "a", "name": "Radio"},
                        {"name": "missing id"},
                    ],
                    "next_cursor": "page-2",
                },
            },
            {"status": 200, "headers": {}, "body": {"items": [{"id": "b", "name": "Clock"}]}},
        ]
    }
    tested = service.test("fixture-stock", offline_fixture=fixture)
    assert tested.status == "PASS"
    assert tested.network == "OFFLINE_FIXTURE"
    assert tested.pages == 2
    assert "body" not in tested.model_dump()

    report = service.sync(
        "fixture-stock",
        resource_id="stock",
        tenant_id="tenant-a",
        fixture=fixture,
        maximum_pages=2,
        canonical_required_fields=("id", "name"),
        now=datetime(2026, 7, 28, tzinfo=UTC),
    )
    assert (report.raw_records, report.canonical_records, report.quarantined_records) == (3, 2, 1)
    assert registry.cursor("fixture-stock", "stock") == "page-2"
    assert registry.inspect("fixture-stock").last_sync is not None


def test_openapi_import_is_review_gated_and_never_activates(tmp_path: Path) -> None:
    source = {
        "openapi": "3.1.0",
        "info": {"title": "Warehouse API", "version": "1.2.0"},
        "servers": [{"url": "https://warehouse.example.test/v1"}],
        "components": {"securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}}},
        "paths": {
            "/stock": {
                "get": {
                    "operationId": "listStock",
                    "parameters": [{"name": "cursor", "in": "query"}],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "items": {"type": "array", "items": {"type": "object"}}
                                        },
                                    }
                                }
                            },
                        }
                    },
                },
                "post": {"operationId": "createStock", "responses": {"201": {"description": "created"}}},
            }
        },
    }
    result = OpenAPIImporter(tmp_path).import_document(source, connector_id="warehouse")
    assert result.manifest_path.exists()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["activation_state"] == "INACTIVE_REVIEW_REQUIRED"
    assert manifest["read_operations"] == ["list-stock"]
    assert manifest["write_operations"] == ["create-stock"]
    assert result.operations == 2
    assert result.unresolved_mappings
    assert (result.connector_path / "openapi-source.json").exists()


def test_durable_workflow_retries_resumes_after_restart_and_approval(tmp_path: Path) -> None:
    path = tmp_path / "workflows.sqlite"
    definitions = WorkflowRegistry()
    definitions.register(
        WorkflowDefinition(
            id="approval-retry",
            version=1,
            input_schema="test",
            steps=[
                WorkflowStepDefinition(
                    id="prepare",
                    handler="prepare",
                    retry_policy=RetryPolicy(maximum_attempts=2, base_delay_seconds=0),
                ),
                WorkflowStepDefinition(
                    id="publish",
                    handler="publish",
                    retry_policy=RetryPolicy(maximum_attempts=1),
                    approval_policy="exact",
                ),
            ],
        )
    )
    attempts = {"prepare": 0}

    def prepare(value: dict[str, object]) -> dict[str, object]:
        attempts["prepare"] += 1
        if attempts["prepare"] == 1:
            raise TimeoutError("temporary")
        return {**value, "prepared": True}

    handlers = {"prepare": prepare, "publish": lambda value: {**value, "published": True}}
    now = datetime(2026, 7, 28, tzinfo=UTC)
    engine = DurableWorkflowEngine(path, definitions, handlers, clock=lambda: now)
    run = engine.start("approval-retry", {"sku": "A"}, idempotency_key="same")
    engine.work_once()
    assert engine.status(run.id).state == WorkflowState.RETRYING
    engine.close()

    restarted = DurableWorkflowEngine(path, definitions, handlers, clock=lambda: now)
    restarted.schedule_due()
    restarted.work_once()
    assert restarted.status(run.id).state == WorkflowState.WAITING_FOR_APPROVAL
    approval_id = restarted.status(run.id).steps[1].approval_id
    assert approval_id
    restarted.approve(run.id, "publish", approval_id=approval_id)
    restarted.work_once()
    completed = restarted.status(run.id)
    assert completed.state == WorkflowState.COMPLETED
    assert completed.steps[0].attempt == 2
    assert completed.steps[1].output_digest
    assert restarted.start("approval-retry", {"sku": "A"}, idempotency_key="same").id == run.id
    restarted.close()


def test_stock_to_offer_definition_runs_only_through_generic_engine(tmp_path: Path) -> None:
    definition = stock_to_offer_definition()
    assert definition.id == "stock-to-offer-v1"
    assert [step.id for step in definition.steps] == [
        "connector-source",
        "persist-raw-record",
        "canonical-stock",
        "calculate-price",
        "estimate-delivery",
        "send-offer",
        "await-webhook",
    ]
    registry = WorkflowRegistry()
    registry.register(definition)
    handlers = {step.handler: (lambda value: {**value, "handled": True}) for step in definition.steps}

    def await_webhook(value: dict[str, object]) -> dict[str, object]:
        raise WaitForExternalEvent("provider-message-1")

    handlers["stock.await_webhook"] = await_webhook
    engine = DurableWorkflowEngine(
        tmp_path / "stock-workflow.sqlite",
        registry,
        handlers,
        clock=lambda: datetime(2026, 7, 28, tzinfo=UTC),
    )
    run = engine.start("stock-to-offer-v1", {"stock": "A"}, idempotency_key="stock-A")
    engine.work_once()
    approval = engine.status(run.id)
    assert approval.state == WorkflowState.WAITING_FOR_APPROVAL
    approval_id = approval.steps[-2].approval_id
    assert approval_id
    engine.approve(run.id, "send-offer", approval_id=approval_id)
    engine.work_once()
    waiting = engine.status(run.id)
    assert waiting.state == WorkflowState.WAITING_FOR_EXTERNAL_EVENT
    assert waiting.steps[-1].external_correlation_id == "provider-message-1"
    engine.signal_external_event(
        run.id,
        "await-webhook",
        correlation_id="provider-message-1",
        payload={"status": "delivered"},
    )
    engine.work_once()
    assert engine.status(run.id).state == WorkflowState.COMPLETED
    engine.close()


def test_meta_and_twilio_adapters_contracts_signatures_and_idempotency() -> None:
    requests: list[ProviderRequest] = []

    def transport(request: ProviderRequest) -> ProviderResponse:
        requests.append(request)
        if request.path.endswith("/phone-1/messages"):
            return ProviderResponse(200, {}, {"messages": [{"id": "wamid.1"}]})
        if request.path.endswith("/Messages.json"):
            return ProviderResponse(201, {}, {"sid": "SM1"})
        if request.path.endswith("/Calls.json"):
            return ProviderResponse(201, {}, {"sid": "CA1"})
        return ProviderResponse(200, {}, {"message_id": "ig.1"})

    secrets = EnvironmentSecretStore(
        {"META_TOKEN": "meta-secret", "META_APP_SECRET": "app-secret", "TWILIO_TOKEN": "twilio-secret"}
    )
    whatsapp = MetaWhatsAppAdapter(
        account_id="phone-1",
        sender="+27110000000",
        token_reference="META_TOKEN",
        app_secret_reference="META_APP_SECRET",
        secret_store=secrets,
        transport=transport,
    )
    instagram = MetaInstagramAdapter(
        account_id="ig-account",
        sender="page-1",
        token_reference="META_TOKEN",
        app_secret_reference="META_APP_SECRET",
        secret_store=secrets,
        transport=transport,
    )
    sms = TwilioSMSAdapter(
        account_sid="AC1",
        auth_token_reference="TWILIO_TOKEN",
        sender="+27110000000",
        callback_url="https://hooks.example.test/twilio/sms",
        secret_store=secrets,
        transport=transport,
    )
    voice = TwilioVoiceAdapter(
        account_sid="AC1",
        auth_token_reference="TWILIO_TOKEN",
        sender="+27110000000",
        callback_url="https://hooks.example.test/twilio/voice",
        secret_store=secrets,
        transport=transport,
    )
    assert whatsapp.send_message("+27820000000", "hello", idempotency_key="msg-1") == "wamid.1"
    assert whatsapp.send_message("+27820000000", "hello", idempotency_key="msg-1") == "wamid.1"
    assert instagram.send_message("recipient-1", "hello", idempotency_key="msg-2") == "ig.1"
    assert sms.send_message("+27820000000", "hello", idempotency_key="msg-3") == "SM1"
    assert (
        voice.place_call(
            "+27820000000", twiml_url="https://voice.example.test/instructions", idempotency_key="msg-4"
        )
        == "CA1"
    )
    assert len(requests) == 4
    assert requests[0].headers["Authorization"] == "Bearer meta-secret"
    assert all("meta-secret" not in json.dumps(request.redacted()) for request in requests)
    body = b'{"entry":[]}'
    signature = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
    assert verify_meta_signature(body, signature, "app-secret")
    assert not verify_meta_signature(body, "sha256=invalid", "app-secret")
    assert voice.recording_enabled is False


def test_smtp_tls_retry_classification_and_webhook_contracts() -> None:
    class FakeSMTP:
        started_tls = False
        logged_in: tuple[str, str] | None = None
        message_id: str | None = None

        def __init__(self, _host: str, _port: int, *, timeout: float) -> None:
            assert timeout == 3

        def __enter__(self) -> "FakeSMTP":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def starttls(self, *, context: object) -> None:
            assert context is not None
            self.started_tls = True

        def login(self, username: str, password: str) -> None:
            self.logged_in = (username, password)

        def send_message(self, message: object) -> dict[str, object]:
            self.message_id = str(message["Message-ID"])  # type: ignore[index]
            return {}

    secrets = EnvironmentSecretStore(
        {"SMTP_USER": "mailer", "SMTP_PASSWORD": "password", "TWILIO_TOKEN": "token"}
    )
    smtp = SMTPAdapter(
        host="smtp.example.test",
        port=587,
        sender="verified@example.test",
        username_reference="SMTP_USER",
        password_reference="SMTP_PASSWORD",
        secret_store=secrets,
        smtp_factory=FakeSMTP,
        timeout_seconds=3,
    )
    reference = smtp.send_email("customer@example.test", "Offer", "Hello", idempotency_key="email-1")
    assert reference == "<email-1@skillshelf.local>"
    assert smtp.send_email("customer@example.test", "Offer", "Hello", idempotency_key="email-1") == reference

    def throttled(_request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(429, {"Retry-After": "2"}, {"error": "rate limit"})

    sms = TwilioSMSAdapter(
        account_sid="AC1",
        auth_token_reference="TWILIO_TOKEN",
        sender="+27110000000",
        callback_url="https://hooks.example.test/twilio",
        secret_store=secrets,
        transport=throttled,
    )
    try:
        sms.send_message("+27820000000", "hello", idempotency_key="sms-1")
    except ProviderSendError as error:
        assert error.retryable
    else:
        raise AssertionError("rate-limited provider response must fail")

    params = {"MessageSid": "SM1", "MessageStatus": "delivered"}
    content = "https://hooks.example.test/twilio" + "".join(f"{key}{params[key]}" for key in sorted(params))
    signature = base64.b64encode(hmac.new(b"token", content.encode(), hashlib.sha1).digest()).decode()
    assert verify_twilio_signature("https://hooks.example.test/twilio", params, signature, "token")
    assert not verify_twilio_signature("https://hooks.example.test/twilio", params, "invalid", "token")
    reconciler = IdempotentWebhookReconciler()
    first = reconciler.reconcile(
        provider="twilio",
        event_id="event-1",
        provider_reference="SM1",
        status="DELIVERED",
    )
    duplicate = reconciler.reconcile(
        provider="twilio",
        event_id="event-1",
        provider_reference="SM1",
        status="DELIVERED",
    )
    assert first.applied
    assert not duplicate.applied
