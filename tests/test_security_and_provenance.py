import hashlib, json, pathlib, re

ROOT = pathlib.Path(__file__).parents[1]

def canonical_bytes(path):
    data = path.read_bytes()
    if b"\0" not in data:
        try:
            data.decode("utf-8")
            return data.replace(b"\r\n", b"\n")
        except UnicodeDecodeError:
            pass
    return data

def test_vendor_hashes():
    manifest = json.loads((ROOT / "vendor-manifest.json").read_text())
    assert len(manifest["files"]) >= 200
    for rel, expected in manifest["files"].items():
        assert hashlib.sha256(canonical_bytes(ROOT / rel)).hexdigest() == expected

def test_no_runtime_secret_artifacts():
    forbidden_names = {".env", "auth.json", "cookies.json"}
    for path in ROOT.rglob("*"):
        if any(part in {".git", ".venv", "work", "upstream"} for part in path.parts):
            continue
        assert path.name not in forbidden_names
        assert not path.name.endswith((".db", ".db-wal", ".db-shm"))

def test_mcp_registry_has_write_confirmations():
    value = (ROOT / "mcp/registry.yml").read_text()
    assert "secret_environment_variables:" in value
    github = value.split("- name: github\n", 1)[1].split("- name:", 1)[0]
    assert "confirmation_required: true" in github

def test_workflows_do_not_expose_pull_request_secrets():
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        value = path.read_text()
        assert "pull_request_target" not in value
        if "pull_request:" in value:
            assert "secrets." not in value
