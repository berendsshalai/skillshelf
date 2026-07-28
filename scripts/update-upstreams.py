#!/usr/bin/env python3
"""Report upstream drift and create a review report; never merge or mutate pins."""
from __future__ import annotations
import argparse
import datetime
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]

def remote_head(repo: str, branch: str) -> str:
    out = subprocess.check_output(["git", "ls-remote", repo, f"refs/heads/{branch}"], text=True, timeout=60)
    return out.split()[0]

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--report", type=pathlib.Path, default=ROOT / "upstream-drift-report.md")
    args = p.parse_args()
    lock = json.loads((ROOT / "upstream-lock.json").read_text(encoding="utf-8"))
    rows, changed = [], 0
    for source in lock["sources"]:
        try:
            latest = remote_head(source["repository"], source["branch"])
            status = "current" if latest == source["commit"] else "drift"
            changed += status == "drift"
        except Exception as exc:
            latest, status = "unavailable", f"error: {type(exc).__name__}"
        rows.append((source["repository"], source["commit"], latest, status))
    lines = [
        "# Upstream drift report", "",
        f"Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}", "",
        "This report is read-only. It does not change submodules, vendor snapshots, locks, branches, or licences.", "",
        "| Repository | Pinned | Latest | Status |", "|---|---|---|---|",
    ]
    lines += [f"| {repo} | `{pin}` | `{latest}` | {status} |" for repo, pin, latest, status in rows]
    lines += ["", "## Review procedure", "",
              "1. Create a staging branch.", "2. Fetch the changed source and inspect its licence/notices.",
              "3. Diff required source files.", "4. Regenerate a complete staged vendor package.",
              "5. Run semantic-preservation, provenance, security, and package tests.",
              "6. Open a draft review; never auto-merge."]
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"checked {len(rows)} sources; {changed} have drift; report: {args.report}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
