#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import statistics
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sdk" / "python" / "src"))
from skillshelf_agents.routing import route_task  # noqa: E402


def estimated_tokens(paths: list[pathlib.Path]) -> int:
    return sum(len(path.read_bytes()) for path in paths) // 4


def main() -> int:
    routing = yaml.safe_load((ROOT / "agents/evals/routing.yml").read_text(encoding="utf-8"))["cases"]
    results = []
    for case in routing:
        decision = route_task(case["task"])
        results.append({"task": case["task"], "expected": case["expected"], "actual": decision.direct_agent,
                        "passed": decision.direct_agent == case["expected"]})
    skill_paths = sorted((ROOT / "skills").glob("*/SKILL.md"))
    eager = estimated_tokens(skill_paths)
    lazy = [estimated_tokens([path]) for path in skill_paths]
    comparison = {
        "method": "deterministic UTF-8 bytes/4 context estimate; no model request",
        "baseline_all_skills_tokens": eager,
        "lazy_specialist_median_tokens": int(statistics.median(lazy)),
        "reduction_tokens": eager - int(statistics.median(lazy)),
        "quality_score": sum(item["passed"] for item in results) / len(results),
        "quality_threshold": 1.0,
        "claim_scope": "skill-file context only; not total paid model usage",
    }
    report = {"routing": results, "token_comparison": comparison}
    destination = ROOT / "agents" / "generated" / "evaluation-report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if all(item["passed"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
