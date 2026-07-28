from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from skillshelf_agents.communications import CommunicationGateway, MessageIntent, MessageStatus
from skillshelf_agents.data import IntegrationDatabase
from skillshelf_agents.data.database import canonical_json, digest
from skillshelf_agents.delivery import DeliveryRequest, DeterministicDeliveryProvider
from skillshelf_agents.pricing import PricingInput, PricingRule, calculate_price, persist_decision


class StockToOfferInput(BaseModel):
    tenant_id: str
    source_system: str
    stock_payload: dict[str, Any]
    observed_at: datetime
    pricing_rule: PricingRule
    delivery_request: DeliveryRequest
    customer_id: str
    consent_reference: str
    channels: list[str]
    approval_required: bool = False


class WorkflowResult(BaseModel):
    run_id: str
    state: Literal["WAITING_FOR_EXTERNAL_EVENT", "COMPLETED", "FAILED"]
    product_id: str
    variant_id: str
    price: str
    delivery_quote_id: str
    message_id: str
    provider_references: dict[str, str]
    evidence_hash: str


class StockToOfferWorkflow:
    workflow_id = "stock-to-offer-v1"

    def __init__(
        self,
        database: IntegrationDatabase,
        delivery: DeterministicDeliveryProvider,
        communications: CommunicationGateway,
    ) -> None:
        self.database = database
        self.delivery = delivery
        self.communications = communications

    def _step(self, run_id: str, step_id: str, evidence: dict[str, Any], now: datetime) -> None:
        self.database.connection.execute(
            """INSERT OR REPLACE INTO workflow_steps VALUES(?,?,?,?,?)""",
            (run_id, step_id, "COMPLETED", canonical_json(evidence), now.isoformat()),
        )

    def run(
        self,
        workflow_input: StockToOfferInput,
        *,
        run_id: str,
        idempotency_key: str,
        authority: set[str],
        now: datetime,
    ) -> WorkflowResult:
        existing = self.database.connection.execute(
            "SELECT id,result_json FROM workflow_runs WHERE tenant_id=? AND workflow_id=? AND idempotency_key=?",
            (workflow_input.tenant_id, self.workflow_id, idempotency_key),
        ).fetchone()
        if existing and existing["result_json"] != "{}":
            return WorkflowResult.model_validate_json(existing["result_json"])
        if existing:
            run_id = str(existing["id"])

        input_hash = digest(workflow_input.model_dump(mode="json"))
        if not existing:
            self.database.connection.execute(
                "INSERT INTO workflow_runs VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    workflow_input.tenant_id,
                    self.workflow_id,
                    idempotency_key,
                    "RUNNING",
                    input_hash,
                    "{}",
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        self.database.connection.commit()
        normalized = self.database.normalize_stock(
            workflow_input.tenant_id,
            workflow_input.source_system,
            workflow_input.stock_payload,
            observed_at=workflow_input.observed_at,
            ingested_at=now,
        )
        if normalized is None:
            self.database.connection.execute(
                "UPDATE workflow_runs SET state='FAILED',updated_at=? WHERE id=?",
                (now.isoformat(), run_id),
            )
            self.database.connection.commit()
            raise ValueError("stock record could not be normalized")
        self._step(run_id, "normalize-stock", {"variant_id": normalized.variant.id}, now)

        decision = calculate_price(
            PricingInput(
                supplier_cost=normalized.supplier_price.amount,
                source_record_ids=[normalized.product.metadata.source_record_id],
                effective_at=workflow_input.observed_at,
            ),
            workflow_input.pricing_rule,
            decision_id=f"{run_id}:price",
        )
        persist_decision(self.database, workflow_input.tenant_id, decision)
        self._step(run_id, "calculate-price", decision.model_dump(mode="json"), now)

        quote = self.delivery.quote(workflow_input.delivery_request)
        quote_payload = quote.model_dump(mode="json")
        self.database.connection.execute(
            "INSERT OR REPLACE INTO delivery_quotes VALUES(?,?,?,?)",
            (quote.id, workflow_input.tenant_id, canonical_json(quote_payload), digest(quote_payload)),
        )
        self._step(run_id, "estimate-delivery", quote_payload, now)

        message_id = f"{run_id}:offer"
        intent = MessageIntent(
            message_id=message_id,
            tenant_id=workflow_input.tenant_id,
            purpose="price_quote",
            customer_id=workflow_input.customer_id,
            locale="en-ZA",
            channels=workflow_input.channels,
            template_id="stock-offer-v1",
            variables={
                "product": normalized.product.name,
                "price": str(decision.selling_price),
                "currency": decision.currency,
                "arrival": quote.estimated_arrival_to.date().isoformat(),
            },
            consent_reference=workflow_input.consent_reference,
            approval_required=workflow_input.approval_required,
            expires_at=quote.expires_at,
        )
        references = self.communications.send(intent, authority=authority, now=now)
        self._step(run_id, "send-offer", {"provider_references": references}, now)
        evidence = {
            "input_hash": input_hash,
            "price_evidence": decision.evidence_hash,
            "delivery_evidence": digest(quote_payload),
            "message_id": message_id,
            "provider_references": references,
        }
        result = WorkflowResult(
            run_id=run_id,
            state="WAITING_FOR_EXTERNAL_EVENT",
            product_id=normalized.product.id,
            variant_id=normalized.variant.id,
            price=str(decision.selling_price),
            delivery_quote_id=quote.id,
            message_id=message_id,
            provider_references=references,
            evidence_hash=digest(evidence),
        )
        self.database.connection.execute(
            "UPDATE workflow_runs SET state=?,result_json=?,updated_at=? WHERE id=?",
            (result.state, result.model_dump_json(), now.isoformat(), run_id),
        )
        self.database.connection.execute(
            "INSERT INTO workflow_events(run_id,event_type,payload,created_at) VALUES(?,?,?,?)",
            (run_id, "offer.accepted", canonical_json(references), now.isoformat()),
        )
        self.database.connection.commit()
        return result

    def reconcile_delivery(
        self,
        *,
        run_id: str,
        provider: str,
        event_id: str,
        provider_reference: str,
        status: MessageStatus,
        payload: dict[str, object],
        received_at: datetime,
    ) -> bool:
        applied = self.communications.reconcile_webhook(
            provider=provider,
            event_id=event_id,
            provider_reference=provider_reference,
            status=status,
            payload=payload,
            received_at=received_at,
        )
        if not applied:
            return False
        row = self.database.connection.execute(
            "SELECT result_json FROM workflow_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        if not row:
            raise KeyError("workflow run not found")
        result = WorkflowResult.model_validate_json(row["result_json"])
        statuses = [
            MessageStatus(item[0])
            for item in self.database.connection.execute(
                "SELECT status FROM message_deliveries WHERE message_id=?",
                (result.message_id,),
            )
        ]
        if statuses and all(
            value in {MessageStatus.DELIVERED, MessageStatus.READ, MessageStatus.REPLIED}
            for value in statuses
        ):
            result.state = "COMPLETED"
            self.database.connection.execute(
                "UPDATE workflow_runs SET state=?,result_json=?,updated_at=? WHERE id=?",
                (result.state, result.model_dump_json(), received_at.isoformat(), run_id),
            )
            self.database.connection.execute(
                "INSERT INTO workflow_events(run_id,event_type,payload,created_at) VALUES(?,?,?,?)",
                (run_id, "offer.delivered", canonical_json(payload), received_at.isoformat()),
            )
            self.database.connection.commit()
        return True
