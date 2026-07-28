from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CanonicalMetadata(BaseModel):
    tenant_id: str
    source_system: str
    source_record_id: str
    schema_version: int = 1
    observed_at: datetime
    effective_at: datetime
    ingested_at: datetime
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    lineage: list[str]
    quality_status: Literal["valid", "quarantined"]


class Product(BaseModel):
    id: str
    name: str
    category_id: str
    metadata: CanonicalMetadata


class ProductVariant(BaseModel):
    id: str
    product_id: str
    sku: str
    metadata: CanonicalMetadata


class InventorySnapshot(BaseModel):
    id: str
    variant_id: str
    location_id: str
    quantity: int = Field(ge=0)
    metadata: CanonicalMetadata


class SupplierPrice(BaseModel):
    id: str
    variant_id: str
    amount: Decimal = Field(gt=0)
    currency: str
    metadata: CanonicalMetadata

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        if len(value) != 3 or not value.isalpha() or value.upper() != value:
            raise ValueError("currency must be an uppercase ISO-like code")
        return value


class NormalizedStock(BaseModel):
    product: Product
    variant: ProductVariant
    inventory: InventorySnapshot
    supplier_price: SupplierPrice
