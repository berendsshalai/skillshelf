from __future__ import annotations

import hashlib
import hmac

import pytest

from skillshelf_agents.communications.providers import (
    IdempotentWebhookReconciler,
    MetaWhatsAppAdapter,
    ProviderRequest,
    ProviderResponse,
    ProviderSendError,
)
from skillshelf_agents.connectors import EnvironmentSecretStore


def test_meta_contract_redacts_secret_retries_and_rejects_invalid_webhook_signature() -> None:
    requests: list[ProviderRequest] = []

    def transport(request: ProviderRequest) -> ProviderResponse:
        requests.append(request)
        if len(requests) == 1:
            return ProviderResponse(429, {"Retry-After": "1"}, {"error": "limited"})
        return ProviderResponse(200, {}, {"messages": [{"id": "wamid.2"}]})

    adapter = MetaWhatsAppAdapter(
        account_id="phone-1",
        sender="+27110000000",
        token_reference="META_TOKEN",
        app_secret_reference="META_APP_SECRET",
        secret_store=EnvironmentSecretStore(
            {"META_TOKEN": "access-secret", "META_APP_SECRET": "signing-secret"}
        ),
        transport=transport,
    )
    with pytest.raises(ProviderSendError) as captured:
        adapter.send_message("+27820000000", "hello", idempotency_key="message-1")
    assert captured.value.retryable
    assert "access-secret" not in str(adapter.request_log)

    assert adapter.send_message("+27820000000", "hello", idempotency_key="message-1") == "wamid.2"
    assert adapter.send_message("+27820000000", "hello", idempotency_key="message-1") == "wamid.2"
    assert len(requests) == 2

    body = b'{"entry":[]}'
    valid = "sha256=" + hmac.new(b"signing-secret", body, hashlib.sha256).hexdigest()
    assert adapter.verify_webhook(body, valid)
    assert not adapter.verify_webhook(body, "sha256=invalid")


def test_provider_webhook_reconciliation_is_idempotent() -> None:
    reconciler = IdempotentWebhookReconciler()
    first = reconciler.reconcile(
        provider="meta-whatsapp",
        event_id="event-1",
        provider_reference="wamid.2",
        status="DELIVERED",
    )
    duplicate = reconciler.reconcile(
        provider="meta-whatsapp",
        event_id="event-1",
        provider_reference="wamid.2",
        status="FAILED",
    )
    assert first.applied
    assert not duplicate.applied
    assert reconciler.statuses[("meta-whatsapp", "wamid.2")] == "DELIVERED"
