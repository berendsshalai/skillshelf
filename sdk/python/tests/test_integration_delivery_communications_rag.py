from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from skillshelf_agents.communications import (
    CommunicationGateway,
    ConsentRecord,
    MessageIntent,
    MessageStatus,
    MockChannelAdapter,
)
from skillshelf_agents.data import IntegrationDatabase
from skillshelf_agents.delivery import (
    Address,
    BusinessCalendar,
    DeliveryRequest,
    DeterministicDeliveryProvider,
    Parcel,
)
from skillshelf_agents.rag import SQLiteKnowledgeBase
from skillshelf_agents.suggestions import CapabilityState, suggest_capabilities


def _delivery_request():
    return DeliveryRequest(
        origin=Address(country="ZA", postal_code="2001", city="Johannesburg"),
        destination=Address(country="ZA", postal_code="8001", city="Cape Town"),
        parcel=Parcel(
            weight_kg=Decimal("1"), length_cm=Decimal("10"), width_cm=Decimal("10"), height_cm=Decimal("10")
        ),
        requested_at=datetime.fromisoformat("2026-07-27T09:00:00+02:00"),
    )


def test_delivery_communications_lifecycle_rag_citations_and_suggestions(tmp_path):
    provider = DeterministicDeliveryProvider(calendar=BusinessCalendar({date(2026, 7, 29)}))
    quote = provider.quote(_delivery_request())
    assert quote.fee == Decimal("89.00")
    assert quote.dispatch_at.date() == date(2026, 7, 28)
    assert quote.estimated_arrival_from.date() == date(2026, 7, 31)
    assert quote.estimated_arrival_to.date() == date(2026, 8, 3)

    database = IntegrationDatabase(tmp_path / "integration.sqlite")
    adapters = [
        MockChannelAdapter("email", sender="offers@example.test"),
        MockChannelAdapter("whatsapp", sender="+27110000000"),
    ]
    gateway = CommunicationGateway(
        database,
        adapters,
        {"offer": "{product}: {currency} {price}"},
    )
    now = datetime(2026, 7, 28, 8, tzinfo=UTC)
    gateway.store_consent(
        ConsentRecord(
            id="consent-1",
            tenant_id="tenant-a",
            customer_id="customer-a",
            purpose="price_quote",
            channel="*",
            granted=True,
            verified_recipient=True,
        )
    )
    intent = MessageIntent(
        message_id="message-1",
        tenant_id="tenant-a",
        purpose="price_quote",
        customer_id="customer-a",
        locale="en-ZA",
        channels=["email", "whatsapp"],
        template_id="offer",
        variables={"product": "Radio", "currency": "ZAR", "price": "156.25"},
        consent_reference="consent-1",
        approval_required=True,
    )
    references = gateway.send(
        intent,
        authority={"send_customer_message", "approve:message-1"},
        now=now,
    )
    assert database.count("message_deliveries") == 2
    for index, reference in enumerate(references.values(), start=1):
        assert gateway.reconcile_webhook(
            provider="mock",
            event_id=f"evt-{index}",
            provider_reference=reference,
            status=MessageStatus.DELIVERED,
            payload={"status": "delivered"},
            received_at=now,
        )
    assert not gateway.reconcile_webhook(
        provider="mock",
        event_id="evt-1",
        provider_reference=references["email"],
        status=MessageStatus.DELIVERED,
        payload={"status": "delivered"},
        received_at=now,
    )

    knowledge = SQLiteKnowledgeBase(tmp_path / "knowledge.sqlite")
    content_hash = knowledge.ingest(
        document_id="policy-1",
        source="operations-manual",
        version="3",
        effective_at=datetime(2026, 7, 1, tzinfo=UTC),
        ingested_at=now,
        sections={"Delivery": "Standard delivery takes two to three business days."},
    )
    results = knowledge.search("delivery business days", retrieved_at=now)
    assert results[0].citation.content_hash == content_hash
    assert results[0].citation.section == "Delivery"
    assert results[0].citation.freshness == "current"
    suggestions = suggest_capabilities(
        CapabilityState(
            has_stock_source=False,
            has_pricing_rule=True,
            has_delivery_provider=False,
            has_customer_consent=True,
            has_message_channel=True,
        )
    )
    assert [item.code for item in suggestions] == ["connect-stock", "configure-delivery"]
    knowledge.close()
    database.close()
