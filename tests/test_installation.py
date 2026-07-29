import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).parents[1]
NAMES = ["find-skills-codex", "superpowers-codex", "codex-memory", "codex-design-intelligence", "codex-skill-governor"]

def ps(command, *args):
    return subprocess.run(["powershell", "-NoProfile", "-File", str(ROOT / "scripts" / command), *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True)

def test_install_reinstall_doctor_uninstall_preserves_unrelated():
    with tempfile.TemporaryDirectory() as raw:
        target = pathlib.Path(raw) / "skills"
        target.mkdir()
        unrelated = target / "user-owned"
        unrelated.mkdir()
        (unrelated / "keep.txt").write_text("keep")
        first = ps("install.ps1", "-TargetRoot", target)
        assert first.returncode == 0, first.stderr
        second = ps("install.ps1", "-TargetRoot", target)
        assert second.returncode == 0, second.stderr
        assert any(p.name.startswith(".skillshelf-backup-") for p in target.iterdir())
        doctor = ps("doctor.ps1", "-TargetRoot", target)
        assert doctor.returncode == 0, doctor.stderr
        for name in NAMES:
            assert (target / name / "SKILL.md").is_file()
        removed = ps("uninstall.ps1", "-TargetRoot", target)
        assert removed.returncode == 0, removed.stderr
        assert (unrelated / "keep.txt").read_text() == "keep"
        assert not any((target / name).exists() for name in NAMES)
