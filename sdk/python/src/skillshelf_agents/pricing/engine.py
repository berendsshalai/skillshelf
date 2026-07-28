from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from skillshelf_agents.data.database import IntegrationDatabase, canonical_json


class PricingRule(BaseModel):
    id: str
    version: int = Field(ge=1)
    currency: str
    target_margin_rate: Decimal = Field(ge=0, lt=1)
    fixed_profit: Decimal = Field(default=Decimal("0"), ge=0)
    payment_fee_rate: Decimal = Field(default=Decimal("0"), ge=0, lt=1)
    handling_fee: Decimal = Field(default=Decimal("0"), ge=0)
    delivery_subsidy: Decimal = Field(default=Decimal("0"), ge=0)
    risk_buffer: Decimal = Field(default=Decimal("0"), ge=0)
    minimum_price: Decimal | None = Field(default=None, ge=0)
    maximum_discount_rate: Decimal | None = Field(default=None, ge=0, lt=1)
    rounding_increment: Decimal = Field(default=Decimal("0.01"), gt=0)
    effective_from: datetime
    effective_to: datetime | None = None

    @field_validator("currency")
    @classmethod
    def currency_code(cls, value: str) -> str:
        if len(value) != 3 or value.upper() != value:
            raise ValueError("currency must be uppercase and three characters")
        return value

    @model_validator(mode="after")
    def effective_window(self) -> "PricingRule":
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be later than effective_from")
        return self


class PricingInput(BaseModel):
    supplier_cost: Decimal = Field(ge=0)
    inbound_freight: Decimal = Field(default=Decimal("0"), ge=0)
    source_record_ids: list[str]
    effective_at: datetime


class PriceDecision(BaseModel):
    id: str
    formula_version: Literal["skillshelf-price-v1"] = "skillshelf-price-v1"
    rule_id: str
    rule_version: int
    landed_cost: Decimal
    unrounded_selling_price: Decimal
    selling_price: Decimal
    currency: str
    rounding_increment: Decimal
    source_record_ids: list[str]
    effective_at: datetime
    approval_state: Literal["not_required", "approval_required", "approved"]
    evidence_hash: str


def _round_up(value: Decimal, increment: Decimal) -> Decimal:
    units = (value / increment).quantize(Decimal("1"), rounding=ROUND_CEILING)
    return (units * increment).quantize(increment)


def calculate_price(
    pricing_input: PricingInput,
    rule: PricingRule,
    *,
    decision_id: str,
    approval_state: Literal["not_required", "approval_required", "approved"] = "not_required",
) -> PriceDecision:
    if pricing_input.effective_at < rule.effective_from:
        raise ValueError("pricing rule is not yet effective")
    if rule.effective_to and pricing_input.effective_at >= rule.effective_to:
        raise ValueError("pricing rule has expired")
    payment_cost = pricing_input.supplier_cost * rule.payment_fee_rate
    landed = (
        pricing_input.supplier_cost
        + pricing_input.inbound_freight
        + rule.handling_fee
        + payment_cost
        + rule.delivery_subsidy
        + rule.risk_buffer
    )
    unrounded = (landed + rule.fixed_profit) / (Decimal("1") - rule.target_margin_rate)
    result = _round_up(unrounded, rule.rounding_increment)
    if rule.minimum_price is not None:
        result = max(result, rule.minimum_price)
    evidence = {
        "input": pricing_input.model_dump(mode="json"),
        "rule": rule.model_dump(mode="json"),
        "formula": "skillshelf-price-v1",
        "landed": str(landed),
        "unrounded": str(unrounded),
        "result": str(result),
    }
    return PriceDecision(
        id=decision_id,
        rule_id=rule.id,
        rule_version=rule.version,
        landed_cost=landed,
        unrounded_selling_price=unrounded,
        selling_price=result,
        currency=rule.currency,
        rounding_increment=rule.rounding_increment,
        source_record_ids=pricing_input.source_record_ids,
        effective_at=pricing_input.effective_at,
        approval_state=approval_state,
        evidence_hash=hashlib.sha256(canonical_json(evidence).encode()).hexdigest(),
    )


def persist_decision(database: IntegrationDatabase, tenant_id: str, decision: PriceDecision) -> None:
    payload = decision.model_dump(mode="json")
    database.connection.execute(
        """INSERT OR REPLACE INTO price_decisions
           (id,tenant_id,input_json,formula_version,rule_id,rule_version,unrounded,result,currency,
            source_record_ids,effective_at,approval_state,evidence_hash)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            decision.id, tenant_id, json.dumps(payload, sort_keys=True), decision.formula_version,
            decision.rule_id, decision.rule_version, str(decision.unrounded_selling_price),
            str(decision.selling_price), decision.currency, json.dumps(decision.source_record_ids),
            decision.effective_at.astimezone(UTC).isoformat(), decision.approval_state,
            decision.evidence_hash,
        ),
    )
    database.connection.commit()
