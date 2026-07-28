#!/usr/bin/env python3
"""Read-only inspection of a local checkout resolved to an immutable commit."""
from __future__ import annotations
import argparse, json, pathlib, re, subprocess

RISK_PATTERNS = {
    "remote execution": re.compile(r"(curl|wget).{0,80}(\\||iex|Invoke-Expression|bash|sh)", re.I),
    "credential access": re.compile(r"(token|password|private[_ -]?key|cookie|authorization)", re.I),
    "destructive command": re.compile(r"(rm\\s+-rf|Remove-Item\\s+.*-Recurse|format\\s+[A-Z]:)", re.I),
    "telemetry": re.compile(r"(telemetry|analytics|sentry|posthog)", re.I),
}

def run(*args: str, cwd: pathlib.Path) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("path", type=pathlib.Path)
    p.add_argument("--repository", required=True)
    p.add_argument("--commit", required=True)
    ns = p.parse_args()
    root = ns.path.resolve()
    head = run("git", "rev-parse", "HEAD", cwd=root)
    if head != ns.commit or not re.fullmatch(r"[0-9a-f]{40}", ns.commit):
        raise SystemExit("checkout HEAD does not match the requested immutable commit")
    licenses = [x.name for x in root.iterdir() if x.is_file() and x.name.lower().startswith(("license", "copying"))]
    risks, skills = [], []
    for path in root.rglob("*"):
        if path.is_symlink():
            risks.append(f"symlink:{path.relative_to(root)}")
            continue
        if path.is_file() and path.stat().st_size <= 2_000_000:
            if path.name == "SKILL.md":
                skills.append(str(path.relative_to(root)).replace("\\\\", "/"))
            if path.suffix.lower() in {".md", ".ps1", ".sh", ".py", ".js", ".mjs", ".cjs", ".ts"}:
                text = path.read_text(encoding="utf-8", errors="replace")
                for label, pattern in RISK_PATTERNS.items():
                    if pattern.search(text):
                        risks.append(f"{label}:{path.relative_to(root)}")
    compatibility = []
    if any((root / p).exists() for p in (".codex-plugin/plugin.json", ".agents/plugins/marketplace.json")):
        compatibility.append("codex-plugin")
    if skills:
        compatibility.append("agent-skill")
    result = {
        "repository": ns.repository, "commit": head,
        "license": ",".join(licenses) if licenses else "UNVERIFIED",
        "skills": skills, "compatibility": compatibility,
        "security": sorted(set(risks)),
        "recommendation": "reject" if not licenses else ("adapt" if risks else "accept"),
    }
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
