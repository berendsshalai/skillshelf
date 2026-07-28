# Delivery

## Purpose

The deterministic delivery provider produces reproducible quote windows for local workflow and policy testing.

## Architecture

`BusinessCalendar` handles weekdays and configured holidays. `DeterministicDeliveryProvider` applies cutoff, handling days, minimum and maximum transit business days, a fixed fee, quote TTL, and deterministic source reference.

## Configuration

Configure holidays, fee, currency, handling days, transit range, daily cutoff, and TTL. Requests require timezone-aware timestamps, origin and destination addresses, and positive parcel dimensions and weight.

## Commands

```powershell
$env:PYTHONPATH='sdk/python/src'
& sdk/python/.venv/Scripts/python.exe -m pytest -q sdk/python/tests/test_integration_delivery_communications_rag.py --basetemp work/pytest-delivery
```

## Examples

A Monday request before cutoff with Tuesday dispatch, a Wednesday holiday, and two-to-three transit business days yields Friday-to-Monday arrival and a fixed `ZAR 89.00` fee.

## Failure Modes

Naive timestamps, non-positive parcel measurements, or invalid model values fail validation. The deterministic provider itself performs no network I/O and therefore has no carrier timeout mode.

## Security Boundaries

Addresses are sensitive customer data. Restrict logs and persistence accordingly. This estimator is advisory and must not be presented as a carrier guarantee.

## Tests

Tests assert exact dispatch and arrival dates across a configured holiday, exact fee, quote expiry, confidence, reference, and limitations.

## Recovery

Recompute with the same request and calendar for the same deterministic result. Recompute after calendar or policy changes with a new effective configuration and preserve previous customer-facing evidence.

## Known Limitations

No live carrier, geocoding, serviceability, traffic, capacity, remote-area surcharge, or tracking API is integrated. The fixed local quote is deterministic proof only; live provider credentials and SLAs are deferred.
