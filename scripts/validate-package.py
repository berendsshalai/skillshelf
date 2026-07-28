#!/usr/bin/env python3
"""Deterministic structural, provenance, security, agent, MCP, and site validation."""
from __future__ import annotations
import hashlib, json, os, pathlib, re, sys, tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPECTED = {
    "find-skills-codex", "superpowers-codex", "codex-memory",
    "codex-design-intelligence", "codex-skill-governor",
}

def canonical_bytes(path: pathlib.Path) -> bytes:
    data = path.read_bytes()
    if b"\0" not in data:
        try:
            data.decode("utf-8")
            return data.replace(b"\r\n", b"\n")
        except UnicodeDecodeError:
            pass
    return data

def fail(message: str) -> None:
    raise AssertionError(message)

def frontmatter(path: pathlib.Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(f"missing frontmatter: {path}")
    try:
        raw = text.split("---\n", 2)[1]
    except IndexError:
        fail(f"invalid frontmatter: {path}")
    out = {}
    for line in raw.splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out

def validate_skills() -> None:
    dirs = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir()}
    if dirs != EXPECTED:
        fail(f"top-level skills differ: expected {sorted(EXPECTED)}, got {sorted(dirs)}")
    names = []
    for directory in sorted(dirs):
        base = ROOT / "skills" / directory
        for required in ("SKILL.md", "README.md", "PROVENANCE.yml", "SEMANTIC_CONTRACT.yml", "UPSTREAM_DIFF.md"):
            if not (base / required).is_file():
                fail(f"missing {directory}/{required}")
        meta = frontmatter(base / "SKILL.md")
        if meta.get("name") != directory:
            fail(f"skill name mismatch: {directory}")
        if not meta.get("description"):
            fail(f"missing description: {directory}")
        names.append(meta["name"])
    if len(names) != len(set(names)):
        fail("duplicate skill names")

def validate_json_toml() -> None:
    json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    market = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
    entry = market["plugins"][0]
    if entry["source"]["path"] != "./plugins/skillshelf":
        fail("repo marketplace must point at canonical plugins/skillshelf package")
    if not all(k in entry["policy"] for k in ("installation", "authentication")) or "category" not in entry:
        fail("marketplace policy incomplete")
    for path in (ROOT / ".codex/agents").glob("*.toml"):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for key in ("name", "description", "developer_instructions"):
            if not data.get(key):
                fail(f"{path}: missing {key}")
        if "Allowed MCP:" not in data["developer_instructions"] and "MCP" in data["developer_instructions"]:
            fail(f"{path}: MCP boundary not explicit")

def validate_plugin_mirror() -> None:
    target = ROOT / "plugins/skillshelf"
    for rel in (".codex-plugin/plugin.json", "LICENSE", "THIRD_PARTY_NOTICES.md", "vendor-manifest.json"):
        if not (target / rel).is_file():
            fail(f"canonical plugin mirror missing: {rel}")
    for skill in EXPECTED:
        source = ROOT / "skills" / skill / "SKILL.md"
        mirror = target / "skills" / skill / "SKILL.md"
        if not mirror.is_file() or mirror.read_bytes() != source.read_bytes():
            fail(f"canonical plugin mirror is stale: {skill}")

def validate_mcp() -> None:
    for name in ("registry.yml", "policy.yml"):
        text = (ROOT / "mcp" / name).read_text(encoding="utf-8")
        if "\t" in text:
            fail(f"tabs forbidden in YAML: {name}")
    registry = (ROOT / "mcp/registry.yml").read_text(encoding="utf-8")
    for field in ("name:", "purpose:", "required_by:", "transport:", "authentication:", "read_tools:",
                  "write_tools:", "confirmation_required:", "data_scope:", "secret_environment_variables:",
                  "installation_status:", "validation_command:", "fallback:"):
        if field not in registry:
            fail(f"MCP registry missing {field}")

def validate_vendor() -> None:
    lock = json.loads((ROOT / "upstream-lock.json").read_text(encoding="utf-8"))
    if len(lock["sources"]) != 7:
        fail("upstream lock must contain six integration sources plus socials")
    for entry in lock["sources"]:
        if not re.fullmatch(r"[0-9a-f]{40}", entry["commit"]):
            fail(f"bad commit for {entry['repository']}")
        if not entry["license"] or not entry["vendor_paths"]:
            fail(f"incomplete provenance for {entry['repository']}")
    manifest_path = ROOT / "vendor-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for rel, expected in manifest["files"].items():
        path = ROOT / rel
        if not path.is_file():
            fail(f"vendored file missing: {rel}")
        actual = hashlib.sha256(canonical_bytes(path)).hexdigest()
        if actual != expected:
            fail(f"vendored hash mismatch: {rel}")

def validate_site() -> None:
    routes = ["", "skills", "architecture", "installation", "provenance", "agents", "mcp", "credits", "socials"]
    for route in routes:
        path = ROOT / "site" / route / "index.html" if route else ROOT / "site/index.html"
        text = path.read_text(encoding="utf-8")
        if 'lang="en-ZA"' not in text or "<title>" not in text or 'rel="canonical"' not in text:
            fail(f"site metadata incomplete: {route or '/'}")
        if "linear-gradient" in text:
            fail(f"generic gradient found: {route or '/'}")
    social = (ROOT / "site/socials/index.html").read_text(encoding="utf-8")
    exact = [
        "https://github.com/berendsshalai",
        "https://www.linkedin.com/in/sha-lai-berends",
        "https://x.com/berendsshalai",
        "https://www.facebook.com/p/Sha-Lai-Berends-61591546301365/",
        "https://www.instagram.com/berendsshalai",
        "https://bit.ly/3sA5312",
        "https://sha-lai-be-2a6c6108-shalaiberends.wix-site-host.com",
    ]
    for url in exact:
        if url not in social:
            fail(f"missing factual social URL: {url}")
    if social.count('class="social-card"') != 7 or 'rel="me noopener noreferrer"' not in social:
        fail("social cards or safe link attributes invalid")

def validate_security() -> None:
    forbidden_paths = [re.compile(r"C:\\\\Users\\\\User", re.I), re.compile(r"/home/[^/<\\s]+")]
    secret_patterns = [
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"\bgh[opusr]_[A-Za-z0-9]{30,}\b"),
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    ]
    skip = {".git", "upstream"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in skip for part in path.parts) or path.stat().st_size > 3_000_000:
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".woff", ".woff2"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.name not in {"MASTER_BUILD_PROMPT.md", "HANDOFF.md", "validate-package.py"}:
            for pattern in forbidden_paths:
                if pattern.search(text):
                    fail(f"developer-specific absolute path in {path.relative_to(ROOT)}")
        for pattern in secret_patterns:
            if pattern.search(text):
                fail(f"possible secret in {path.relative_to(ROOT)}")

def main() -> int:
    validate_skills()
    validate_json_toml()
    validate_plugin_mirror()
    validate_mcp()
    validate_vendor()
    validate_site()
    validate_security()
    print("SkillShelf package validation passed")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
