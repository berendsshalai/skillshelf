from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, field_validator

from skillshelf_agents.data.database import IntegrationDatabase, canonical_json, digest


class MessageStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    QUEUED = "QUEUED"
    ACCEPTED_BY_PROVIDER = "ACCEPTED_BY_PROVIDER"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    REPLIED = "REPLIED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNSUBSCRIBED = "UNSUBSCRIBED"
    BOUNCED = "BOUNCED"
    NO_ANSWER = "NO_ANSWER"


ORDER = {
    MessageStatus.DRAFT: 0,
    MessageStatus.APPROVAL_REQUIRED: 1,
    MessageStatus.QUEUED: 2,
    MessageStatus.ACCEPTED_BY_PROVIDER: 3,
    MessageStatus.SENT: 4,
    MessageStatus.DELIVERED: 5,
    MessageStatus.READ: 6,
    MessageStatus.REPLIED: 7,
}
TERMINAL_FAILURES = {
    MessageStatus.FAILED, MessageStatus.REJECTED, MessageStatus.EXPIRED,
    MessageStatus.UNSUBSCRIBED, MessageStatus.BOUNCED, MessageStatus.NO_ANSWER,
}


class ConsentRecord(BaseModel):
    id: str
    tenant_id: str
    customer_id: str
    purpose: str
    channel: str
    granted: bool
    verified_recipient: bool
    expires_at: datetime | None = None


class MessageIntent(BaseModel):
    message_id: str
    tenant_id: str
    purpose: Literal["price_quote", "availability", "delivery_update", "order_follow_up"]
    customer_id: str
    locale: str
    channels: list[str]
    template_id: str
    variables: dict[str, str]
    consent_reference: str
    approval_required: bool
    expires_at: datetime | None = None

    @field_validator("channels")
    @classmethod
    def channels_are_distinct(cls, value: list[str]) -> list[str]:
        if not value or len(value) != len(set(value)):
            raise ValueError("channels must be non-empty and unique")
        return value


class ChannelAdapter(Protocol):
    channel: str
    sender: str | None

    def send(self, intent: MessageIntent, rendered: str) -> str: ...


class MockChannelAdapter:
    def __init__(self, channel: Literal["email", "whatsapp"], sender: str | None = None) -> None:
        self.channel = channel
        self.sender = sender
        self.sent: list[tuple[str, str]] = []

    def send(self, intent: MessageIntent, rendered: str) -> str:
        if not self.sender:
            raise RuntimeError(f"{self.channel} sender is not configured")
        reference = hashlib.sha256(f"{self.channel}|{intent.message_id}|{rendered}".encode()).hexdigest()[:24]
        self.sent.append((intent.message_id, rendered))
        return f"mock-{self.channel}-{reference}"


class CommunicationGateway:
    def __init__(
        self,
        database: IntegrationDatabase,
        adapters: list[ChannelAdapter],
        templates: dict[str, str],
    ) -> None:
        self.database = database
        self.adapters = {adapter.channel: adapter for adapter in adapters}
        self.templates = templates

    def store_consent(self, consent: ConsentRecord) -> None:
        self.database.connection.execute(
            "INSERT OR REPLACE INTO consents VALUES(?,?,?,?,?,?,?,?)",
            (
                consent.id, consent.tenant_id, consent.customer_id, consent.purpose, consent.channel,
                int(consent.granted), consent.expires_at.isoformat() if consent.expires_at else None,
                consent.model_dump_json(),
            ),
        )
        self.database.connection.commit()

    def _consent(self, intent: MessageIntent, channel: str, now: datetime) -> ConsentRecord:
        row = self.database.connection.execute(
            "SELECT payload FROM consents WHERE id=? AND tenant_id=?",
            (intent.consent_reference, intent.tenant_id),
        ).fetchone()
        if not row:
            raise PermissionError("consent record not found")
        consent = ConsentRecord.model_validate_json(row["payload"])
        if (
            not consent.granted
            or not consent.verified_recipient
            or consent.customer_id != intent.customer_id
            or consent.purpose != intent.purpose
            or consent.channel not in {channel, "*"}
            or (consent.expires_at and consent.expires_at <= now)
        ):
            raise PermissionError("consent does not authorize this communication")
        return consent

    def send(
        self, intent: MessageIntent, *, authority: set[str], now: datetime,
    ) -> dict[str, str]:
        if "send_customer_message" not in authority:
            raise PermissionError("workflow lacks outbound communication authority")
        if intent.approval_required and f"approve:{intent.message_id}" not in authority:
            raise PermissionError("message requires exact approval")
        if intent.expires_at and intent.expires_at <= now:
            raise PermissionError("message intent expired")
        template = self.templates.get(intent.template_id)
        if template is None:
            raise ValueError("approved template is not configured")
        try:
            rendered = template.format_map(intent.variables)
        except KeyError as error:
            raise ValueError(f"template variable is missing: {error.args[0]}") from error
        self.database.connection.execute(
            "INSERT OR IGNORE INTO message_intents VALUES(?,?,?,?)",
            (intent.message_id, intent.tenant_id, intent.model_dump_json(), MessageStatus.QUEUED),
        )
        results: dict[str, str] = {}
        for channel in intent.channels:
            self._consent(intent, channel, now)
            adapter = self.adapters.get(channel)
            if not adapter or not adapter.sender:
                raise RuntimeError(f"channel is not ready: {channel}")
            existing = self.database.connection.execute(
                "SELECT provider_reference FROM message_deliveries WHERE message_id=? AND channel=?",
                (intent.message_id, channel),
            ).fetchone()
            if existing:
                results[channel] = str(existing["provider_reference"])
                continue
            provider_reference = adapter.send(intent, rendered)
            delivery_id = f"{intent.message_id}:{channel}"
            payload = {
                "delivery_id": delivery_id,
                "message_id": intent.message_id,
                "channel": channel,
                "provider_reference": provider_reference,
                "status": MessageStatus.ACCEPTED_BY_PROVIDER,
            }
            self.database.connection.execute(
                "INSERT INTO message_deliveries VALUES(?,?,?,?,?,?)",
                (
                    delivery_id, intent.message_id, channel, provider_reference,
                    MessageStatus.ACCEPTED_BY_PROVIDER, canonical_json(payload),
                ),
            )
            results[channel] = provider_reference
        self.database.connection.execute(
            "UPDATE message_intents SET status=? WHERE id=?",
            (MessageStatus.ACCEPTED_BY_PROVIDER, intent.message_id),
        )
        self.database.connection.commit()
        return results

    def reconcile_webhook(
        self,
        *,
        provider: str,
        event_id: str,
        provider_reference: str,
        status: MessageStatus,
        payload: dict[str, object],
        received_at: datetime,
    ) -> bool:
        payload_hash = digest(payload)
        inserted = self.database.connection.execute(
            "INSERT OR IGNORE INTO webhook_receipts VALUES(?,?,?,?)",
            (provider, event_id, payload_hash, received_at.isoformat()),
        ).rowcount
        if not inserted:
            self.database.connection.commit()
            return False
        row = self.database.connection.execute(
            "SELECT id,status,payload,message_id FROM message_deliveries WHERE provider_reference=?",
            (provider_reference,),
        ).fetchone()
        if not row:
            self.database.connection.rollback()
            raise KeyError("webhook provider reference is unknown")
        current = MessageStatus(row["status"])
        should_apply = status in TERMINAL_FAILURES or (
            current not in TERMINAL_FAILURES and ORDER.get(status, -1) >= ORDER.get(current, -1)
        )
        if should_apply:
            delivery_payload = json.loads(row["payload"])
            delivery_payload["status"] = status
            delivery_payload["last_event_id"] = event_id
            self.database.connection.execute(
                "UPDATE message_deliveries SET status=?,payload=? WHERE id=?",
                (status, canonical_json(delivery_payload), row["id"]),
            )
            statuses = {
                MessageStatus(item[0])
                for item in self.database.connection.execute(
                    "SELECT status FROM message_deliveries WHERE message_id=?", (row["message_id"],),
                )
            }
            intent_status = min(statuses, key=lambda value: ORDER.get(value, 99))
            if statuses and all(value in {MessageStatus.DELIVERED, MessageStatus.READ, MessageStatus.REPLIED} for value in statuses):
                intent_status = MessageStatus.DELIVERED
            self.database.connection.execute(
                "UPDATE message_intents SET status=? WHERE id=?", (intent_status, row["message_id"]),
            )
        self.database.connection.commit()
        return should_apply
