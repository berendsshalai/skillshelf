from __future__ import annotations

from pydantic import BaseModel


class CapabilityState(BaseModel):
    has_stock_source: bool
    has_pricing_rule: bool
    has_delivery_provider: bool
    has_customer_consent: bool
    has_message_channel: bool


class Suggestion(BaseModel):
    code: str
    message: str
    priority: int


RULES = (
    ("connect-stock", "Connect a stock source before building offers.", 100, "has_stock_source"),
    ("configure-pricing", "Configure an effective pricing rule.", 90, "has_pricing_rule"),
    ("configure-delivery", "Configure a delivery provider for customer estimates.", 80, "has_delivery_provider"),
    ("capture-consent", "Capture verified customer consent before messaging.", 70, "has_customer_consent"),
    ("configure-channel", "Configure a verified outbound messaging channel.", 60, "has_message_channel"),
)


def suggest_capabilities(state: CapabilityState) -> list[Suggestion]:
    return [
        Suggestion(code=code, message=message, priority=priority)
        for code, message, priority, field in RULES
        if not getattr(state, field)
    ]
