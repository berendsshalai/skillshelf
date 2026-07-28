from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class Address(BaseModel):
    country: str
    postal_code: str
    city: str


class Parcel(BaseModel):
    weight_kg: Decimal = Field(gt=0)
    length_cm: Decimal = Field(gt=0)
    width_cm: Decimal = Field(gt=0)
    height_cm: Decimal = Field(gt=0)


class DeliveryRequest(BaseModel):
    origin: Address
    destination: Address
    parcel: Parcel
    requested_at: datetime
    service_preferences: list[str] = Field(default_factory=list)

    @field_validator("requested_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("requested_at must be timezone-aware")
        return value


class DeliveryQuote(BaseModel):
    id: str
    provider: str
    service: str
    fee: Decimal
    currency: str
    dispatch_at: datetime
    estimated_arrival_from: datetime
    estimated_arrival_to: datetime
    expires_at: datetime
    confidence: Decimal = Field(ge=0, le=1)
    source_reference: str
    limitations: list[str]


class BusinessCalendar:
    def __init__(self, holidays: set[date] | None = None) -> None:
        self.holidays = holidays or set()

    def is_business_day(self, value: date) -> bool:
        return value.weekday() < 5 and value not in self.holidays

    def add_business_days(self, value: date, days: int) -> date:
        current = value
        remaining = days
        while remaining:
            current += timedelta(days=1)
            if self.is_business_day(current):
                remaining -= 1
        return current

    def next_business_day(self, value: date) -> date:
        return self.add_business_days(value, 1)


class DeterministicDeliveryProvider:
    def __init__(
        self,
        *,
        calendar: BusinessCalendar,
        fee: Decimal = Decimal("89.00"),
        currency: str = "ZAR",
        handling_business_days: int = 1,
        transit_min_business_days: int = 2,
        transit_max_business_days: int = 3,
        cutoff: time = time(14, 0),
        quote_ttl: timedelta = timedelta(minutes=30),
    ) -> None:
        self.calendar = calendar
        self.fee = fee
        self.currency = currency
        self.handling_days = handling_business_days
        self.transit_min = transit_min_business_days
        self.transit_max = transit_max_business_days
        self.cutoff = cutoff
        self.quote_ttl = quote_ttl

    def quote(self, request: DeliveryRequest) -> DeliveryQuote:
        requested_local = request.requested_at
        starting_date = requested_local.date()
        if not self.calendar.is_business_day(starting_date) or requested_local.timetz().replace(tzinfo=None) >= self.cutoff:
            starting_date = self.calendar.next_business_day(starting_date)
        dispatch_date = self.calendar.add_business_days(starting_date, self.handling_days)
        dispatch = datetime.combine(dispatch_date, time(9, 0), tzinfo=requested_local.tzinfo)
        arrival_from = datetime.combine(
            self.calendar.add_business_days(dispatch_date, self.transit_min), time(8, 0),
            tzinfo=requested_local.tzinfo,
        )
        arrival_to = datetime.combine(
            self.calendar.add_business_days(dispatch_date, self.transit_max), time(18, 0),
            tzinfo=requested_local.tzinfo,
        )
        reference_input = (
            f"{request.origin.postal_code}|{request.destination.postal_code}|"
            f"{request.parcel.weight_kg}|{request.requested_at.isoformat()}"
        )
        reference = hashlib.sha256(reference_input.encode()).hexdigest()[:20]
        return DeliveryQuote(
            id=f"delivery-{reference}",
            provider="skillshelf-deterministic",
            service="standard",
            fee=self.fee,
            currency=self.currency,
            dispatch_at=dispatch,
            estimated_arrival_from=arrival_from,
            estimated_arrival_to=arrival_to,
            expires_at=request.requested_at + self.quote_ttl,
            confidence=Decimal("0.90"),
            source_reference=reference,
            limitations=[
                "Estimate excludes provider disruptions and inaccessible destinations.",
                "Arrival is a range, not a guarantee.",
            ],
        )
