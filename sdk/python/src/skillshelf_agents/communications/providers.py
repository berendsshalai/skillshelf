from __future__ import annotations

import base64
import hashlib
import hmac
import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel

from skillshelf_agents.connectors.secrets import SecretStore

from .gateway import MessageIntent, MessageStatus


REDACTED_HEADERS = {"authorization", "x-api-key", "proxy-authorization"}


@dataclass(frozen=True)
class ProviderRequest:
    method: str
    path: str
    headers: dict[str, str]
    json_body: dict[str, Any] | None = None
    form_body: dict[str, str] | None = None

    def redacted(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "headers": {
                key: ("[REDACTED]" if key.lower() in REDACTED_HEADERS else value)
                for key, value in self.headers.items()
            },
            "json_body": self.json_body,
            "form_body": self.form_body,
        }


@dataclass(frozen=True)
class ProviderResponse:
    status_code: int
    headers: dict[str, str]
    body: dict[str, Any]


class ProviderTransport(Protocol):
    def __call__(self, request: ProviderRequest) -> ProviderResponse: ...


class ProviderSendError(RuntimeError):
    def __init__(self, provider: str, status_code: int, *, retryable: bool) -> None:
        super().__init__(f"{provider} rejected the request ({status_code})")
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable


class WebhookResult(BaseModel):
    provider: str
    event_id: str
    provider_reference: str
    status: MessageStatus
    applied: bool


class IdempotentWebhookReconciler:
    def __init__(self) -> None:
        self._events: set[tuple[str, str]] = set()
        self.statuses: dict[tuple[str, str], MessageStatus] = {}

    def reconcile(
        self,
        *,
        provider: str,
        event_id: str,
        provider_reference: str,
        status: MessageStatus,
    ) -> WebhookResult:
        resolved_status = MessageStatus(status)
        key = (provider, event_id)
        applied = key not in self._events
        if applied:
            self._events.add(key)
            self.statuses[(provider, provider_reference)] = resolved_status
        return WebhookResult(
            provider=provider,
            event_id=event_id,
            provider_reference=provider_reference,
            status=resolved_status,
            applied=applied,
        )


def verify_meta_signature(body: bytes, signature: str, app_secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.removeprefix("sha256="), expected)


def verify_meta_challenge(mode: str, verify_token: str, expected_token: str, challenge: str) -> str:
    if mode != "subscribe" or not hmac.compare_digest(verify_token, expected_token):
        raise PermissionError("invalid Meta webhook challenge")
    return challenge


def verify_twilio_signature(url: str, parameters: dict[str, str], signature: str, auth_token: str) -> bool:
    content = url + "".join(f"{key}{parameters[key]}" for key in sorted(parameters))
    expected = base64.b64encode(
        hmac.new(auth_token.encode(), content.encode(), hashlib.sha1).digest()
    ).decode()
    return hmac.compare_digest(signature, expected)


def _phone(value: str) -> str:
    if not re.fullmatch(r"\+[1-9]\d{7,14}", value):
        raise ValueError("recipient must be an E.164 phone number")
    return value


class _HTTPAdapter:
    channel: str

    def __init__(self, *, sender: str, transport: ProviderTransport) -> None:
        if not sender:
            raise ValueError("configured sender is required")
        self.sender = sender
        self.transport = transport
        self._idempotency: dict[str, str] = {}
        self.request_log: list[dict[str, Any]] = []

    def _send(self, request: ProviderRequest, idempotency_key: str, reference_path: tuple[str, ...]) -> str:
        if existing := self._idempotency.get(idempotency_key):
            return existing
        self.request_log.append(request.redacted())
        response = self.transport(request)
        if response.status_code >= 400:
            raise ProviderSendError(
                self.channel,
                response.status_code,
                retryable=response.status_code in {408, 429, 500, 502, 503, 504},
            )
        value: Any = response.body
        for part in reference_path:
            if isinstance(value, list):
                value = value[int(part)]
            elif isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
            if value is None:
                raise ValueError(f"{self.channel} response omitted provider reference")
        reference = str(value)
        self._idempotency[idempotency_key] = reference
        return reference


class MetaWhatsAppAdapter(_HTTPAdapter):
    channel = "whatsapp"

    def __init__(
        self,
        *,
        account_id: str,
        sender: str,
        token_reference: str,
        app_secret_reference: str,
        secret_store: SecretStore,
        transport: ProviderTransport,
    ) -> None:
        super().__init__(sender=sender, transport=transport)
        self.account_id = account_id
        self.token_reference = token_reference
        self.app_secret_reference = app_secret_reference
        self.secret_store = secret_store

    def send_message(
        self,
        recipient: str,
        text: str,
        *,
        idempotency_key: str,
        template_name: str | None = None,
        consent: bool = True,
    ) -> str:
        if not consent:
            raise PermissionError("WhatsApp consent is required")
        recipient = _phone(recipient)
        if len(text.encode()) > 4096:
            raise ValueError("WhatsApp payload exceeds 4096 bytes")
        message: dict[str, Any]
        if template_name:
            message = {"type": "template", "template": {"name": template_name, "language": {"code": "en"}}}
        else:
            message = {"type": "text", "text": {"body": text}}
        body = {"messaging_product": "whatsapp", "to": recipient, **message}
        request = ProviderRequest(
            "POST",
            f"/v20.0/{self.account_id}/messages",
            {
                "Authorization": f"Bearer {self.secret_store.get(self.token_reference)}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            json_body=body,
        )
        return self._send(request, idempotency_key, ("messages", "0", "id"))

    def send(self, intent: MessageIntent, rendered: str) -> str:
        return self.send_message(intent.customer_id, rendered, idempotency_key=intent.message_id)

    def verify_webhook(self, body: bytes, signature: str) -> bool:
        return verify_meta_signature(body, signature, self.secret_store.get(self.app_secret_reference))


class MetaInstagramAdapter(_HTTPAdapter):
    channel = "instagram"

    def __init__(
        self,
        *,
        account_id: str,
        sender: str,
        token_reference: str,
        app_secret_reference: str,
        secret_store: SecretStore,
        transport: ProviderTransport,
    ) -> None:
        super().__init__(sender=sender, transport=transport)
        self.account_id = account_id
        self.token_reference = token_reference
        self.app_secret_reference = app_secret_reference
        self.secret_store = secret_store

    def send_message(self, recipient: str, text: str, *, idempotency_key: str, consent: bool = True) -> str:
        if not consent or not recipient.strip():
            raise PermissionError("Instagram recipient consent is required")
        if len(text.encode()) > 1000:
            raise ValueError("Instagram payload exceeds 1000 bytes")
        request = ProviderRequest(
            "POST",
            f"/v20.0/{self.account_id}/messages",
            {
                "Authorization": f"Bearer {self.secret_store.get(self.token_reference)}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            json_body={"recipient": {"id": recipient}, "message": {"text": text}},
        )
        return self._send(request, idempotency_key, ("message_id",))

    def send(self, intent: MessageIntent, rendered: str) -> str:
        return self.send_message(intent.customer_id, rendered, idempotency_key=intent.message_id)

    def verify_webhook(self, body: bytes, signature: str) -> bool:
        return verify_meta_signature(body, signature, self.secret_store.get(self.app_secret_reference))


class _TwilioAdapter(_HTTPAdapter):
    def __init__(
        self,
        *,
        account_sid: str,
        auth_token_reference: str,
        sender: str,
        callback_url: str,
        secret_store: SecretStore,
        transport: ProviderTransport,
    ) -> None:
        super().__init__(sender=sender, transport=transport)
        self.account_sid = account_sid
        self.auth_token_reference = auth_token_reference
        self.callback_url = callback_url
        self.secret_store = secret_store

    def _authorization(self) -> str:
        token = base64.b64encode(
            f"{self.account_sid}:{self.secret_store.get(self.auth_token_reference)}".encode()
        ).decode()
        return f"Basic {token}"

    def verify_callback(self, url: str, parameters: dict[str, str], signature: str) -> bool:
        return verify_twilio_signature(
            url, parameters, signature, self.secret_store.get(self.auth_token_reference)
        )


class TwilioSMSAdapter(_TwilioAdapter):
    channel = "sms"

    def send_message(self, recipient: str, text: str, *, idempotency_key: str) -> str:
        recipient = _phone(recipient)
        if len(text) > 1600:
            raise ValueError("SMS payload exceeds 1600 characters")
        request = ProviderRequest(
            "POST",
            f"/2010-04-01/Accounts/{self.account_sid}/Messages.json",
            {"Authorization": self._authorization(), "Idempotency-Key": idempotency_key},
            form_body={
                "To": recipient,
                "From": self.sender,
                "Body": text,
                "StatusCallback": self.callback_url,
            },
        )
        return self._send(request, idempotency_key, ("sid",))

    def send(self, intent: MessageIntent, rendered: str) -> str:
        return self.send_message(intent.customer_id, rendered, idempotency_key=intent.message_id)


class TwilioVoiceAdapter(_TwilioAdapter):
    channel = "voice"
    recording_enabled = False

    def place_call(self, recipient: str, *, twiml_url: str, idempotency_key: str) -> str:
        recipient = _phone(recipient)
        if not twiml_url.startswith("https://"):
            raise ValueError("Twilio voice instructions must use HTTPS")
        request = ProviderRequest(
            "POST",
            f"/2010-04-01/Accounts/{self.account_sid}/Calls.json",
            {"Authorization": self._authorization(), "Idempotency-Key": idempotency_key},
            form_body={
                "To": recipient,
                "From": self.sender,
                "Url": twiml_url,
                "StatusCallback": self.callback_url,
                "Record": "false",
            },
        )
        return self._send(request, idempotency_key, ("sid",))


SMTPFactory = Callable[..., smtplib.SMTP]


class SMTPAdapter:
    channel = "email"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        sender: str,
        username_reference: str,
        password_reference: str,
        secret_store: SecretStore,
        smtp_factory: SMTPFactory = smtplib.SMTP,
        timeout_seconds: float = 10,
    ) -> None:
        if parseaddr(sender)[1] != sender:
            raise ValueError("verified sender must be a valid email address")
        self.host = host
        self.port = port
        self.sender = sender
        self.username_reference = username_reference
        self.password_reference = password_reference
        self.secret_store = secret_store
        self.smtp_factory = smtp_factory
        self.timeout_seconds = timeout_seconds
        self._idempotency: dict[str, str] = {}

    def send_email(
        self,
        recipient: str,
        subject: str,
        text: str,
        *,
        idempotency_key: str,
    ) -> str:
        if parseaddr(recipient)[1] != recipient:
            raise ValueError("recipient must be a valid email address")
        if existing := self._idempotency.get(idempotency_key):
            return existing
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = recipient
        message["Subject"] = subject
        message["Message-ID"] = f"<{idempotency_key}@skillshelf.local>"
        message["X-SkillShelf-Idempotency-Key"] = idempotency_key
        message.set_content(text)
        with self.smtp_factory(self.host, self.port, timeout=self.timeout_seconds) as client:
            client.starttls(context=ssl.create_default_context())
            client.login(
                self.secret_store.get(self.username_reference),
                self.secret_store.get(self.password_reference),
            )
            rejected = client.send_message(message)
        if rejected:
            raise ProviderSendError("smtp", 550, retryable=False)
        reference = str(message["Message-ID"])
        self._idempotency[idempotency_key] = reference
        return reference

    def send(self, intent: MessageIntent, rendered: str) -> str:
        return self.send_email(
            intent.customer_id,
            f"SkillShelf {intent.purpose.replace('_', ' ')}",
            rendered,
            idempotency_key=intent.message_id,
        )


STATUS_MAP: dict[str, MessageStatus] = {
    "accepted": MessageStatus.ACCEPTED_BY_PROVIDER,
    "queued": MessageStatus.QUEUED,
    "sent": MessageStatus.SENT,
    "delivered": MessageStatus.DELIVERED,
    "read": MessageStatus.READ,
    "failed": MessageStatus.FAILED,
    "undelivered": MessageStatus.FAILED,
    "bounced": MessageStatus.BOUNCED,
    "no-answer": MessageStatus.NO_ANSWER,
}


class AdapterReadiness(BaseModel):
    channel: str
    status: Literal[
        "CONFIGURED",
        "READY",
        "DEGRADED",
        "MISSING_SECRET",
        "INVALID_SENDER",
        "UNREACHABLE",
        "SKIPPED",
    ]
    detail: str


class CommunicationsDoctor:
    """Configuration-only readiness checks. It never sends a customer message."""

    def inspect(self, adapters: list[Any]) -> list[AdapterReadiness]:
        results: list[AdapterReadiness] = []
        for adapter in adapters:
            channel = str(getattr(adapter, "channel", "unknown"))
            sender = getattr(adapter, "sender", None)
            if not sender:
                results.append(
                    AdapterReadiness(channel=channel, status="INVALID_SENDER", detail="sender missing")
                )
                continue
            try:
                secret_store = getattr(adapter, "secret_store", None)
                references = [
                    getattr(adapter, name)
                    for name in (
                        "token_reference",
                        "app_secret_reference",
                        "auth_token_reference",
                        "username_reference",
                        "password_reference",
                    )
                    if getattr(adapter, name, None)
                ]
                if secret_store:
                    for reference in references:
                        secret_store.get(reference)
            except (KeyError, ValueError):
                results.append(
                    AdapterReadiness(channel=channel, status="MISSING_SECRET", detail="secret unresolved")
                )
                continue
            results.append(AdapterReadiness(channel=channel, status="READY", detail="configuration valid"))
        return results
