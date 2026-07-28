from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from skillshelf_agents.data import IntegrationDatabase
from skillshelf_agents.pricing import PricingInput, PricingRule, calculate_price, persist_decision


FIXTURES = Path(__file__).parent / "fixtures" / "integration"


def test_raw_canonical_quarantine_and_decimal_golden(tmp_path):
    database = IntegrationDatabase(tmp_path / "integration.sqlite")
    database.map_category("tenant-a", "supplier-a", "electronics", "category-electronics")
    valid = json.loads((FIXTURES / "stock_valid.json").read_text())
    invalid = json.loads((FIXTURES / "stock_invalid.json").read_text())
    observed = datetime(2026, 7, 28, 8, tzinfo=UTC)
    normalized = database.normalize_stock("tenant-a", "supplier-a", valid, observed_at=observed)
    duplicate = database.normalize_stock("tenant-a", "supplier-a", valid, observed_at=observed)
    quarantined = database.normalize_stock("tenant-a", "supplier-a", invalid, observed_at=observed)
    assert normalized is not None and duplicate is not None
    assert normalized.inventory.quantity == 7
    assert quarantined is None
    assert database.count("source_records") == 2
    assert database.count("quarantines") == 1

    rule = PricingRule.model_validate_json((FIXTURES / "pricing_rule.json").read_text())
    decision = calculate_price(
        PricingInput(
            supplier_cost=Decimal("100.00"),
            source_record_ids=["stock-001"],
            effective_at=observed,
        ),
        rule,
        decision_id="price-001",
    )
    persist_decision(database, "tenant-a", decision)
    assert decision.selling_price == Decimal("156.25")
    assert decision.landed_cost == Decimal("125.00")
    assert database.count("price_decisions") == 1
    database.close()
