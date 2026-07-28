from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import (
    CanonicalMetadata,
    InventorySnapshot,
    NormalizedStock,
    Product,
    ProductVariant,
    SupplierPrice,
)


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS source_records (
  id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL, source_system TEXT NOT NULL,
  source_record_id TEXT NOT NULL, observed_at TEXT NOT NULL, content_hash TEXT NOT NULL,
  payload TEXT NOT NULL, headers TEXT NOT NULL,
  UNIQUE(tenant_id, source_system, source_record_id, content_hash)
);
CREATE TABLE IF NOT EXISTS category_mappings (
  tenant_id TEXT NOT NULL, source_system TEXT NOT NULL, source_category TEXT NOT NULL,
  category_id TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY(tenant_id, source_system, source_category)
);
CREATE TABLE IF NOT EXISTS products (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL, category_id TEXT NOT NULL,
  metadata TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS product_variants (
  id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES products(id), sku TEXT NOT NULL UNIQUE,
  metadata TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inventory_snapshots (
  id TEXT PRIMARY KEY, variant_id TEXT NOT NULL REFERENCES product_variants(id),
  location_id TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity >= 0), metadata TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS supplier_prices (
  id TEXT PRIMARY KEY, variant_id TEXT NOT NULL REFERENCES product_variants(id),
  amount TEXT NOT NULL, currency TEXT NOT NULL, metadata TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quarantines (
  id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL, source_record_id TEXT NOT NULL,
  reason TEXT NOT NULL, payload_hash TEXT NOT NULL, first_observed TEXT NOT NULL,
  latest_observed TEXT NOT NULL, resolution_state TEXT NOT NULL DEFAULT 'open',
  UNIQUE(tenant_id, source_record_id, reason)
);
CREATE TABLE IF NOT EXISTS price_decisions (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, input_json TEXT NOT NULL, formula_version TEXT NOT NULL,
  rule_id TEXT NOT NULL, rule_version INTEGER NOT NULL, unrounded TEXT NOT NULL, result TEXT NOT NULL,
  currency TEXT NOT NULL, source_record_ids TEXT NOT NULL, effective_at TEXT NOT NULL,
  approval_state TEXT NOT NULL, evidence_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS delivery_quotes (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, payload TEXT NOT NULL, evidence_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS consents (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, customer_id TEXT NOT NULL, purpose TEXT NOT NULL,
  channel TEXT NOT NULL, granted INTEGER NOT NULL, expires_at TEXT, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS message_intents (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS message_deliveries (
  id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES message_intents(id), channel TEXT NOT NULL,
  provider_reference TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL,
  UNIQUE(message_id, channel)
);
CREATE TABLE IF NOT EXISTS webhook_receipts (
  provider TEXT NOT NULL, event_id TEXT NOT NULL, payload_hash TEXT NOT NULL, received_at TEXT NOT NULL,
  PRIMARY KEY(provider, event_id)
);
CREATE TABLE IF NOT EXISTS workflow_runs (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, workflow_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
  state TEXT NOT NULL, input_hash TEXT NOT NULL, result_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(tenant_id, workflow_id, idempotency_key)
);
CREATE TABLE IF NOT EXISTS workflow_steps (
  run_id TEXT NOT NULL REFERENCES workflow_runs(id), step_id TEXT NOT NULL, state TEXT NOT NULL,
  evidence_json TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(run_id, step_id)
);
CREATE TABLE IF NOT EXISTS workflow_events (
  id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES workflow_runs(id),
  event_type TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class IntegrationDatabase:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def map_category(
        self,
        tenant_id: str,
        source_system: str,
        source_category: str,
        category_id: str,
    ) -> None:
        self.connection.execute(
            """INSERT INTO category_mappings VALUES(?,?,?,?,1)
               ON CONFLICT(tenant_id,source_system,source_category)
               DO UPDATE SET category_id=excluded.category_id,version=version+1""",
            (tenant_id, source_system, source_category, category_id),
        )
        self.connection.commit()

    def store_raw(
        self,
        tenant_id: str,
        source_system: str,
        source_record_id: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        observed_at: datetime,
    ) -> tuple[int, str]:
        payload_hash = digest(payload)
        cursor = self.connection.execute(
            """INSERT OR IGNORE INTO source_records
               (tenant_id,source_system,source_record_id,observed_at,content_hash,payload,headers)
               VALUES(?,?,?,?,?,?,?)""",
            (
                tenant_id,
                source_system,
                source_record_id,
                observed_at.isoformat(),
                payload_hash,
                canonical_json(payload),
                canonical_json(headers),
            ),
        )
        if cursor.lastrowid:
            record_id = int(cursor.lastrowid)
        else:
            row = self.connection.execute(
                """SELECT id FROM source_records WHERE tenant_id=? AND source_system=?
                   AND source_record_id=? AND content_hash=?""",
                (tenant_id, source_system, source_record_id, payload_hash),
            ).fetchone()
            record_id = int(row["id"])
        self.connection.commit()
        return record_id, payload_hash

    def quarantine(
        self,
        tenant_id: str,
        source_record_id: str,
        reason: str,
        payload_hash: str,
        at: datetime,
    ) -> None:
        self.connection.execute(
            """INSERT INTO quarantines
               (tenant_id,source_record_id,reason,payload_hash,first_observed,latest_observed)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(tenant_id,source_record_id,reason)
               DO UPDATE SET latest_observed=excluded.latest_observed,payload_hash=excluded.payload_hash""",
            (tenant_id, source_record_id, reason, payload_hash, at.isoformat(), at.isoformat()),
        )
        self.connection.commit()

    def normalize_stock(
        self,
        tenant_id: str,
        source_system: str,
        payload: dict[str, Any],
        *,
        observed_at: datetime,
        ingested_at: datetime | None = None,
    ) -> NormalizedStock | None:
        ingested = ingested_at or datetime.now(UTC)
        external_id = str(payload.get("id", "")).strip()
        raw_id, content_hash = self.store_raw(
            tenant_id,
            source_system,
            external_id or "missing-id",
            payload,
            {},
            observed_at,
        )
        required = ("id", "name", "sku", "category", "location_id", "stock", "supplier_price", "currency")
        missing = [name for name in required if payload.get(name) in (None, "")]
        if missing:
            self.quarantine(
                tenant_id,
                external_id or "missing-id",
                f"missing:{','.join(missing)}",
                content_hash,
                observed_at,
            )
            return None
        mapping = self.connection.execute(
            """SELECT category_id FROM category_mappings
               WHERE tenant_id=? AND source_system=? AND source_category=?""",
            (tenant_id, source_system, str(payload["category"])),
        ).fetchone()
        if not mapping:
            self.quarantine(tenant_id, external_id, "unmapped_category", content_hash, observed_at)
            return None
        try:
            metadata = CanonicalMetadata(
                tenant_id=tenant_id,
                source_system=source_system,
                source_record_id=external_id,
                observed_at=observed_at,
                effective_at=observed_at,
                ingested_at=ingested,
                content_hash=content_hash,
                lineage=[f"source_records:{raw_id}"],
                quality_status="valid",
            )
            product = Product(
                id=f"{tenant_id}:product:{external_id}",
                name=str(payload["name"]),
                category_id=str(mapping["category_id"]),
                metadata=metadata,
            )
            variant = ProductVariant(
                id=f"{tenant_id}:variant:{payload['sku']}",
                product_id=product.id,
                sku=str(payload["sku"]),
                metadata=metadata,
            )
            inventory = InventorySnapshot(
                id=f"{variant.id}:{observed_at.isoformat()}",
                variant_id=variant.id,
                location_id=str(payload["location_id"]),
                quantity=int(payload["stock"]),
                metadata=metadata,
            )
            supplier = SupplierPrice(
                id=f"{variant.id}:supplier:{observed_at.isoformat()}",
                variant_id=variant.id,
                amount=Decimal(str(payload["supplier_price"])),
                currency=str(payload["currency"]),
                metadata=metadata,
            )
        except (ValidationError, ValueError, ArithmeticError) as error:
            self.quarantine(tenant_id, external_id, f"validation:{error}", content_hash, observed_at)
            return None
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO products VALUES(?,?,?,?,?)",
                (
                    product.id,
                    tenant_id,
                    product.name,
                    product.category_id,
                    product.metadata.model_dump_json(),
                ),
            )
            self.connection.execute(
                "INSERT OR REPLACE INTO product_variants VALUES(?,?,?,?)",
                (variant.id, variant.product_id, variant.sku, variant.metadata.model_dump_json()),
            )
            self.connection.execute(
                "INSERT OR REPLACE INTO inventory_snapshots VALUES(?,?,?,?,?)",
                (
                    inventory.id,
                    inventory.variant_id,
                    inventory.location_id,
                    inventory.quantity,
                    inventory.metadata.model_dump_json(),
                ),
            )
            self.connection.execute(
                "INSERT OR REPLACE INTO supplier_prices VALUES(?,?,?,?,?)",
                (
                    supplier.id,
                    supplier.variant_id,
                    str(supplier.amount),
                    supplier.currency,
                    supplier.metadata.model_dump_json(),
                ),
            )
        return NormalizedStock(
            product=product,
            variant=variant,
            inventory=inventory,
            supplier_price=supplier,
        )

    def count(self, table: str) -> int:
        allowed = {
            "source_records",
            "products",
            "product_variants",
            "inventory_snapshots",
            "supplier_prices",
            "quarantines",
            "price_decisions",
            "delivery_quotes",
            "message_intents",
            "message_deliveries",
            "webhook_receipts",
            "workflow_runs",
            "workflow_steps",
            "workflow_events",
        }
        if table not in allowed:
            raise ValueError("unknown table")
        return int(self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
