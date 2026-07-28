import pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).parents[3]
SCRIPT = ROOT / "skills/find-skills-codex/scripts/inspect_skill.py"

def test_help():
    result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "--commit" in result.stdout
