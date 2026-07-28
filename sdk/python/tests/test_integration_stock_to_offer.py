from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from skillshelf_agents.communications import (
    CommunicationGateway,
    ConsentRecord,
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
from skillshelf_agents.pricing import PricingRule
from skillshelf_agents.workflows import StockToOfferInput, StockToOfferWorkflow


FIXTURES = Path(__file__).parent / "fixtures" / "integration"


def _services(path):
    database = IntegrationDatabase(path)
    gateway = CommunicationGateway(
        database,
        [
            MockChannelAdapter("email", sender="offers@example.test"),
            MockChannelAdapter("whatsapp", sender="+27110000000"),
        ],
        {"stock-offer-v1": "{product}: {currency} {price}, arrives by {arrival}"},
    )
    workflow = StockToOfferWorkflow(
        database,
        DeterministicDeliveryProvider(calendar=BusinessCalendar()),
        gateway,
    )
    return database, gateway, workflow


def test_durable_idempotent_stock_to_offer_and_webhook_restart(tmp_path):
    path = tmp_path / "workflow.sqlite"
    database, gateway, workflow = _services(path)
    database.map_category("tenant-a", "supplier-a", "electronics", "category-electronics")
    gateway.store_consent(
        ConsentRecord(
            id="consent-1", tenant_id="tenant-a", customer_id="customer-a",
            purpose="price_quote", channel="*", granted=True, verified_recipient=True,
        )
    )
    observed = datetime(2026, 7, 28, 8, tzinfo=UTC)
    workflow_input = StockToOfferInput(
        tenant_id="tenant-a",
        source_system="supplier-a",
        stock_payload=json.loads((FIXTURES / "stock_valid.json").read_text()),
        observed_at=observed,
        pricing_rule=PricingRule.model_validate_json((FIXTURES / "pricing_rule.json").read_text()),
        delivery_request=DeliveryRequest(
            origin=Address(country="ZA", postal_code="2001", city="Johannesburg"),
            destination=Address(country="ZA", postal_code="8001", city="Cape Town"),
            parcel=Parcel(weight_kg=Decimal("1"), length_cm=Decimal("10"), width_cm=Decimal("10"), height_cm=Decimal("10")),
            requested_at=datetime.fromisoformat("2026-07-28T10:00:00+02:00"),
        ),
        customer_id="customer-a",
        consent_reference="consent-1",
        channels=["email", "whatsapp"],
    )
    first = workflow.run(
        workflow_input, run_id="run-1", idempotency_key="stock-001-v1",
        authority={"send_customer_message"}, now=observed,
    )
    second = workflow.run(
        workflow_input, run_id="ignored-run", idempotency_key="stock-001-v1",
        authority={"send_customer_message"}, now=observed,
    )
    assert first == second
    assert first.price == "156.25"
    assert database.count("workflow_runs") == 1
    assert database.count("message_deliveries") == 2
    references = first.provider_references
    database.close()

    database, _gateway, workflow = _services(path)
    assert workflow.reconcile_delivery(
        run_id="run-1", provider="mock", event_id="evt-email",
        provider_reference=references["email"], status=MessageStatus.DELIVERED,
        payload={"status": "delivered"}, received_at=observed,
    )
    assert workflow.reconcile_delivery(
        run_id="run-1", provider="mock", event_id="evt-whatsapp",
        provider_reference=references["whatsapp"], status=MessageStatus.DELIVERED,
        payload={"status": "delivered"}, received_at=observed,
    )
    row = database.connection.execute(
        "SELECT state,result_json FROM workflow_runs WHERE id='run-1'",
    ).fetchone()
    assert row["state"] == "COMPLETED"
    assert json.loads(row["result_json"])["state"] == "COMPLETED"
    assert database.count("webhook_receipts") == 2
    assert not workflow.reconcile_delivery(
        run_id="run-1", provider="mock", event_id="evt-email",
        provider_reference=references["email"], status=MessageStatus.DELIVERED,
        payload={"status": "delivered"}, received_at=observed,
    )
    assert database.count("webhook_receipts") == 2
    database.close()
