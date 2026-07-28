# Pricing

## Purpose

The pricing engine produces auditable selling prices with exact decimal arithmetic and versioned rule evidence.

## Architecture

`PricingInput` supplies supplier cost, inbound freight, source record IDs, and effective time. `PricingRule` supplies fees, buffers, fixed profit, target margin, minimum, rounding increment, and effective window. `PriceDecision` records inputs, formula version, result, approval state, and evidence hash.

## Configuration

Use uppercase three-character currency codes and decimal strings. The rule must be effective at decision time. Target margin must be below one, and the rounding increment must be positive.

## Commands

```powershell
$env:PYTHONPATH='sdk/python/src'
& sdk/python/.venv/Scripts/python.exe -m pytest -q sdk/python/tests/test_integration_data_pricing.py --basetemp work/pytest-pricing
```

## Examples

With supplier cost `100.00`, handling `25.00`, target margin `0.20`, and no other adjustments, landed cost is `125.00` and selling price is exactly `156.25`.

## Failure Modes

Rules outside their effective window, invalid decimal ranges, malformed currencies, or impossible model values fail validation. Database persistence errors propagate.

## Security Boundaries

Rules are caller-supplied policy inputs, not user-controlled suggestions. Authorize rule creation and selection separately. Evidence hashes detect changed inputs but do not provide signatures or access control.

## Tests

The golden integration test asserts landed cost `125.00`, selling price `156.25`, and exactly one persisted price decision.

## Recovery

Correct or version the pricing rule, then create a new decision ID. Retain prior decisions for audit rather than overwriting business history; the current persistence helper uses replace semantics if the same ID is deliberately reused.

## Known Limitations

Tax, tiered fees, promotions, discount enforcement, exchange rates, and approval workflow policy are not calculated. The mock proof uses ZAR and a single fixed formula version; live commercial rules remain deferred.
