#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sdk" / "python" / "src"))

from skillshelf_agents.agent_factory import AgentFactory  # noqa: E402
from skillshelf_agents.config import Settings  # noqa: E402
from skillshelf_agents.orchestrator import SkillShelfOrchestrator  # noqa: E402
from skillshelf_agents.registry import RuntimeRegistry  # noqa: E402
from skillshelf_agents.skill_loader import SkillLoader  # noqa: E402

SECRET_PATTERN = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._-]+|gh[pousr]_[A-Za-z0-9]{12,})"
)


def sanitise(value: object) -> str:
    return SECRET_PATTERN.sub("[REDACTED]", str(value))[:2000]


def digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_at(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for component in path.split("."):
        if not isinstance(value, dict) or component not in value:
            raise KeyError(path)
        value = value[component]
    return value


def text_at(payload: dict[str, Any], path: str) -> str:
    value = value_at(payload, path)
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


def grounded_file_evidence(
    payload: dict[str, Any],
    relative: str,
    *,
    require_exact_content: bool,
) -> tuple[bool, str]:
    path = (ROOT / relative).resolve()
    if ROOT not in path.parents or not path.is_file():
        return False, f"fixture source is not a repository file: {relative}"
    expected = path.read_text(encoding="utf-8").strip()
    evidence = payload.get("evidence", [])
    matching = [
        item
        for item in evidence
        if relative.casefold()
        in f"{item.get('source', '')} {item.get('location', '')}".casefold()
    ]
    combined = "\n".join(
        [str(payload.get("answer", "")), *(str(item.get("summary", "")) for item in matching)]
    )
    exact_content = expected in combined
    passed = bool(matching) and (exact_content or not require_exact_content)
    return (
        passed,
        f"source={relative!r}, matched_evidence={len(matching)}, exact_content={exact_content}",
    )


def grounded_file_digest(payload: dict[str, Any], relative: str) -> tuple[bool, str]:
    expected = digest((ROOT / relative).resolve())
    evidence = payload.get("evidence", [])
    matching = [
        item
        for item in evidence
        if relative.casefold()
        in f"{item.get('source', '')} {item.get('location', '')}".casefold()
    ]
    combined = "\n".join(
        [str(payload.get("answer", "")), *(str(item.get("summary", "")) for item in matching)]
    )
    digest_present = expected is not None and expected in combined
    return (
        bool(matching) and digest_present,
        f"source={relative!r}, matched_evidence={len(matching)}, exact_digest={digest_present}",
    )


def evaluate_assertion(
    assertion: dict[str, Any],
    payload: dict[str, Any],
    *,
    before: dict[str, str | None],
    prior_canaries: list[str],
) -> tuple[bool, str]:
    kind = assertion["type"]
    if kind == "files_unchanged":
        changed = [
            relative
            for relative, previous in before.items()
            if digest(ROOT / relative) != previous
        ]
        return not changed, f"changed={changed}"
    if kind == "no_prior_canaries":
        rendered = json.dumps(payload, sort_keys=True)
        leaked = [canary for canary in prior_canaries if canary in rendered]
        return not leaked, f"leaked_prior_canaries={leaked}"
    if kind == "grounded_file_evidence":
        return grounded_file_evidence(
            payload,
            str(assertion["file"]),
            require_exact_content=bool(assertion.get("require_exact_content", False)),
        )
    if kind == "grounded_file_digest":
        return grounded_file_digest(payload, str(assertion["file"]))

    path = str(assertion["path"])
    try:
        value = value_at(payload, path)
    except KeyError:
        return False, f"missing result path: {path}"
    if kind == "equals":
        expected = assertion["expected"]
        return value == expected, f"actual={value!r}, expected={expected!r}"
    if kind == "in":
        expected = assertion["expected"]
        return value in expected, f"actual={value!r}, allowed={expected!r}"
    if kind == "contains":
        expected = assertion["expected"]
        return expected in value, f"actual={value!r}, expected_member={expected!r}"
    if kind == "not_contains":
        expected = str(assertion["expected"]).casefold()
        actual = text_at(payload, path).casefold()
        return expected not in actual, f"forbidden={expected!r}, present={expected in actual}"
    if kind == "any_contains":
        actual = text_at(payload, path).casefold()
        expected = [str(item).casefold() for item in assertion["expected"]]
        matches = [item for item in expected if item in actual]
        return bool(matches), f"matched={matches}, expected_any={expected}"
    if kind == "min_items":
        minimum = int(assertion["minimum"])
        return len(value) >= minimum, f"count={len(value)}, minimum={minimum}"
    if kind == "max_items":
        maximum_items = int(assertion["maximum"])
        return (
            len(value) <= maximum_items,
            f"count={len(value)}, maximum={maximum_items}",
        )
    if kind == "max_value":
        maximum_value = float(assertion["maximum"])
        return (
            float(value) <= maximum_value,
            f"actual={value}, maximum={maximum_value}",
        )
    raise ValueError(f"unsupported assertion type: {kind}")


def failure_report(output: Path, message: str, *, code: str) -> None:
    report = {
        "schema_version": 1,
        "suite": "credentialed-operational-agent-evals",
        "status": "ERROR",
        "started_at": datetime.now(UTC).isoformat(),
        "summary": {"score": 0, "passed": 0, "failed": 1},
        "fixtures": [],
        "failures": [{"fixture": None, "phase": "startup", "code": code, "message": sanitise(message)}],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


async def execute_fixture(
    fixture: dict[str, Any],
    settings: Settings,
    prior_canaries: list[str],
) -> dict[str, Any]:
    fixture_id = str(fixture["id"])
    canary = f"SKILLSHELF_EVAL_CANARY_{fixture_id}_{uuid.uuid4().hex}"
    prompt = (
        f"Private evaluation canary for this isolated session: {canary}. "
        "Never include the canary in your output.\n\n"
        + str(fixture["prompt"]).replace("{{canary}}", canary)
    )
    protected = [str(path) for path in fixture.get("protect_paths", ())]
    before = {relative: digest(ROOT / relative) for relative in protected}
    session_id = f"credentialed-eval-{fixture_id}-{uuid.uuid4().hex}"
    registry = RuntimeRegistry.load(ROOT)
    runtime = SkillShelfOrchestrator(
        registry,
        AgentFactory(registry, SkillLoader(ROOT)),
        settings,
    )
    started = time.perf_counter()
    payload: dict[str, Any] = {}
    execution_error: dict[str, str] | None = None
    try:
        result = await runtime.run(
            prompt,
            session_id=session_id,
            explicit_agent=fixture.get("explicit_agent"),
        )
        payload = result.model_dump(mode="json")
    except Exception as exc:
        execution_error = {"type": type(exc).__name__, "message": sanitise(exc)}
    latency = time.perf_counter() - started

    assertions: list[dict[str, Any]] = []
    for assertion in fixture["assertions"]:
        if execution_error is not None:
            passed, detail = False, f"execution failed: {execution_error['type']}"
        else:
            try:
                passed, detail = evaluate_assertion(
                    assertion,
                    payload,
                    before=before,
                    prior_canaries=prior_canaries,
                )
            except Exception as exc:
                passed, detail = False, f"assertion error: {sanitise(exc)}"
        assertions.append(
            {
                "type": assertion["type"],
                "passed": passed,
                "detail": detail,
                "required": bool(assertion.get("required", True)),
            }
        )

    ceilings = fixture["ceilings"]
    used_tokens = int(payload.get("usage", {}).get("total_tokens", 0))
    ceiling_checks = [
        {
            "type": "token_ceiling",
            "passed": execution_error is None and used_tokens <= int(ceilings["total_tokens"]),
            "detail": f"actual={used_tokens}, maximum={ceilings['total_tokens']}",
            "required": True,
        },
        {
            "type": "latency_ceiling",
            "passed": latency <= float(ceilings["latency_seconds"]),
            "detail": f"actual={latency:.3f}, maximum={ceilings['latency_seconds']}",
            "required": True,
        },
    ]
    assertions.extend(ceiling_checks)
    passed_count = sum(item["passed"] for item in assertions)
    score = passed_count / len(assertions)
    fixture_passed = execution_error is None and all(
        item["passed"] for item in assertions if item["required"]
    )
    prior_canaries.append(canary)
    return {
        "id": fixture_id,
        "category": fixture["category"],
        "required": bool(fixture.get("required", True)),
        "weight": float(fixture.get("weight", 1)),
        "status": "PASS" if fixture_passed else "FAIL",
        "score": round(score, 4),
        "session_id": session_id,
        "latency_seconds": round(latency, 3),
        "total_tokens": used_tokens,
        "specialists_used": payload.get("specialists_used", []),
        "assertions": assertions,
        "execution_error": execution_error,
    }


def validate_suite(document: dict[str, Any]) -> None:
    if document.get("schema_version") != 1:
        raise ValueError("credentialed fixture schema_version must be 1")
    suite = document.get("suite")
    fixtures = document.get("fixtures")
    if not isinstance(suite, dict) or not isinstance(fixtures, list) or not fixtures:
        raise ValueError("credentialed suite and non-empty fixtures are required")
    required_categories = {
        "routing",
        "ambiguity_and_minimum_specialists",
        "real_tool_grounding_and_source_evidence",
        "unsupported_claim_rejection",
        "approval",
        "budget",
        "failure_recovery",
        "context_isolation",
    }
    categories = {fixture.get("category") for fixture in fixtures}
    missing = sorted(required_categories - categories)
    if missing:
        raise ValueError(f"credentialed fixture categories missing: {missing}")
    ids = [fixture.get("id") for fixture in fixtures]
    if len(ids) != len(set(ids)):
        raise ValueError("credentialed fixture ids must be unique")
    supported_assertions = {
        "any_contains",
        "contains",
        "equals",
        "files_unchanged",
        "grounded_file_digest",
        "grounded_file_evidence",
        "in",
        "max_items",
        "max_value",
        "min_items",
        "no_prior_canaries",
        "not_contains",
    }
    for fixture in fixtures:
        if not fixture.get("assertions"):
            raise ValueError(f"{fixture.get('id')}: assertions are required")
        unknown_assertions = {
            assertion.get("type")
            for assertion in fixture["assertions"]
            if assertion.get("type") not in supported_assertions
        }
        if unknown_assertions:
            raise ValueError(
                f"{fixture.get('id')}: unsupported assertions: {sorted(unknown_assertions)}"
            )
        ceilings = fixture.get("ceilings", {})
        if int(ceilings.get("total_tokens", 0)) <= 0:
            raise ValueError(f"{fixture.get('id')}: positive token ceiling is required")
        if float(ceilings.get("latency_seconds", 0)) <= 0:
            raise ValueError(f"{fixture.get('id')}: positive latency ceiling is required")


async def run_suite(document: dict[str, Any], output: Path) -> int:
    suite = document["suite"]
    started_at = datetime.now(UTC)
    started = time.perf_counter()
    prior_canaries: list[str] = []
    with tempfile.TemporaryDirectory(prefix="skillshelf-credentialed-evals-") as directory:
        settings = Settings(
            home=Path(directory),
            soft_token_limit=int(os.getenv("SKILLSHELF_SOFT_TOKEN_LIMIT", "24000")),
            hard_token_limit=int(os.getenv("SKILLSHELF_HARD_TOKEN_LIMIT", "36000")),
            trace_include_sensitive=False,
        )
        fixture_results = []
        for fixture in document["fixtures"]:
            fixture_results.append(await execute_fixture(fixture, settings, prior_canaries))

    total_weight = sum(item["weight"] for item in fixture_results)
    weighted_score = sum(item["score"] * item["weight"] for item in fixture_results) / total_weight
    total_tokens = sum(item["total_tokens"] for item in fixture_results)
    total_latency = time.perf_counter() - started
    failures = [
        {
            "fixture": item["id"],
            "phase": "execution" if item["execution_error"] else "assertion",
            "code": (
                item["execution_error"]["type"]
                if item["execution_error"]
                else "mechanical_assertion_failed"
            ),
            "message": (
                item["execution_error"]["message"]
                if item["execution_error"]
                else "; ".join(
                    check["detail"] for check in item["assertions"] if not check["passed"]
                )
            ),
        }
        for item in fixture_results
        if item["status"] == "FAIL"
    ]
    if total_tokens > int(suite["max_total_tokens"]):
        failures.append(
            {
                "fixture": None,
                "phase": "suite_ceiling",
                "code": "total_token_ceiling_exceeded",
                "message": (
                    f"actual={total_tokens}, maximum={int(suite['max_total_tokens'])}"
                ),
            }
        )
    if total_latency > float(suite["max_total_latency_seconds"]):
        failures.append(
            {
                "fixture": None,
                "phase": "suite_ceiling",
                "code": "total_latency_ceiling_exceeded",
                "message": (
                    f"actual={total_latency:.3f}, "
                    f"maximum={float(suite['max_total_latency_seconds'])}"
                ),
            }
        )
    required_ok = all(
        item["status"] == "PASS" for item in fixture_results if item["required"]
    )
    ceilings_ok = (
        total_tokens <= int(suite["max_total_tokens"])
        and total_latency <= float(suite["max_total_latency_seconds"])
    )
    passed = (
        weighted_score >= float(suite["pass_score"])
        and ceilings_ok
        and (required_ok or not suite.get("require_all_required_fixtures", True))
    )
    report = {
        "schema_version": 1,
        "suite": suite["name"],
        "status": "PASS" if passed else "FAIL",
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "summary": {
            "score": round(weighted_score, 4),
            "pass_score": suite["pass_score"],
            "passed": sum(item["status"] == "PASS" for item in fixture_results),
            "failed": sum(item["status"] == "FAIL" for item in fixture_results),
            "total_tokens": total_tokens,
            "max_total_tokens": suite["max_total_tokens"],
            "total_latency_seconds": round(total_latency, 3),
            "max_total_latency_seconds": suite["max_total_latency_seconds"],
        },
        "fixtures": fixture_results,
        "failures": failures,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run scored, credentialed SkillShelf evaluations.")
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=ROOT / "agents" / "evals" / "credentialed.yml",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "credentialed-eval.json")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        document = yaml.safe_load(args.fixtures.read_text(encoding="utf-8"))
        validate_suite(document)
    except Exception as exc:
        failure_report(args.output, str(exc), code="invalid_fixture_suite")
        print(f"Credentialed evaluation fixture validation failed: {sanitise(exc)}", file=sys.stderr)
        return 2
    if args.validate_only:
        print(f"Validated {len(document['fixtures'])} credentialed fixtures.")
        return 0
    if not os.getenv("OPENAI_API_KEY"):
        message = "OPENAI_API_KEY is required for credentialed agent evaluations"
        failure_report(args.output, message, code="missing_openai_api_key")
        print(message, file=sys.stderr)
        return 2
    return asyncio.run(run_suite(document, args.output))


if __name__ == "__main__":
    raise SystemExit(main())
