from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "governor.py"
SPEC = importlib.util.spec_from_file_location("governor", SCRIPT)
assert SPEC and SPEC.loader
governor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(governor)


class GovernorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "state"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def observation(self, index: int = 0) -> dict[str, object]:
        return {
            "skill": "example-skill",
            "type": "repeated-failure",
            "issue": f"failure {index}",
            "suggested_improvement": "add a deterministic gate",
            "principle": "repeatable failures need mechanical checks",
            "evidence": [f"evidence/{index}.md"],
        }

    def make_skill(self, name: str = "live") -> Path:
        skill = Path(self.temporary.name) / name
        (skill / "references").mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: example-skill\ndescription: Example.\n---\n"
            "Read references/rules.md.\n",
            encoding="utf-8",
        )
        (skill / "references" / "rules.md").write_text("safe\n", encoding="utf-8")
        return skill

    def test_state_layout_and_doctor(self) -> None:
        result = governor.doctor(self.root)
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["auto_modify_live_skills"])
        for directory in governor.STATE_DIRS:
            self.assertTrue((self.root / directory).is_dir())

    def test_codex_home_override(self) -> None:
        prior = os.environ.get("CODEX_HOME")
        os.environ["CODEX_HOME"] = str(Path(self.temporary.name) / "codex")
        try:
            expected = Path(os.environ["CODEX_HOME"]) / "state" / "skillshelf-governor"
            self.assertEqual(governor.resolve_state_root(), expected.resolve())
        finally:
            if prior is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = prior

    def test_observation_backup_and_survival(self) -> None:
        identifier, backup = governor.add_observation(self.root, self.observation())
        self.assertTrue(backup.is_file())
        records = governor.list_observations(self.root, "OPEN")
        self.assertEqual([record["id"] for record in records], [identifier])
        self.assertEqual(records[0]["kind"], "skill-governance-observation")

    def test_concurrent_writers_do_not_lose_records(self) -> None:
        governor.init_state(self.root)

        def write(index: int) -> str:
            return governor.add_observation(self.root, self.observation(index))[0]

        with ThreadPoolExecutor(max_workers=8) as executor:
            identifiers = list(executor.map(write, range(32)))
        records = governor.list_observations(self.root)
        self.assertEqual(len(records), 32)
        self.assertEqual(len(set(identifiers)), 32)
        self.assertEqual({record["id"] for record in records}, set(identifiers))
        self.assertFalse(any((self.root / "locks").iterdir()))

    def test_process_level_concurrency(self) -> None:
        governor.init_state(self.root)
        processes = []
        for index in range(10):
            command = [
                sys.executable,
                str(SCRIPT),
                "--state-root",
                str(self.root),
                "observe",
                "--skill",
                "example-skill",
                "--type",
                "workflow-discovery",
                "--issue",
                f"issue {index}",
                "--suggested-improvement",
                "stage a bounded improvement",
                "--principle",
                "evidence should survive concurrent writers",
                "--evidence",
                f"evidence/{index}.md",
            ]
            processes.append(
                subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            )
        results = [process.communicate(timeout=30) + (process.returncode,) for process in processes]
        self.assertTrue(all(result[2] == 0 for result in results), results)
        self.assertEqual(len(governor.list_observations(self.root)), 10)

    def test_lock_timeout_and_owned_release(self) -> None:
        governor.init_state(self.root)
        first = governor.FileLock(self.root, "test", timeout=0.2, stale_after=60)
        second = governor.FileLock(self.root, "test", timeout=0.05, stale_after=60)
        first.acquire()
        with self.assertRaises(governor.GovernorError):
            second.acquire()
        first.release()
        self.assertFalse((self.root / "locks" / "test.lock").exists())

    def test_stale_lock_is_recovered(self) -> None:
        governor.init_state(self.root)
        lock_path = self.root / "locks" / "stale.lock"
        lock_path.write_text('{"token":"abandoned"}', encoding="utf-8")
        old = time.time() - 60
        os.utime(lock_path, (old, old))
        lock = governor.FileLock(self.root, "stale", timeout=1, stale_after=1)
        lock.acquire()
        metadata = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["token"], lock.token)
        lock.release()

    def test_observation_resolution_is_bounded(self) -> None:
        first, _ = governor.add_observation(self.root, self.observation(1))
        second, _ = governor.add_observation(self.root, self.observation(2))
        resolved, backup = governor.resolve_observation(
            self.root, first, "ACTIONED", "staged package verified"
        )
        records = {item["id"]: item for item in governor.list_observations(self.root)}
        self.assertTrue(backup.exists())
        self.assertEqual(resolved["status"], "ACTIONED")
        self.assertEqual(records[first]["status"], "ACTIONED")
        self.assertEqual(records[second]["status"], "OPEN")

    def test_cross_cutting_principle_has_separate_schema(self) -> None:
        identifier, backup = governor.add_principle(
            self.root,
            "Verify narrow layouts",
            "Mobile overflow requires a mechanical viewport gate.",
            ["evidence/mobile.md"],
        )
        records = governor.list_principles(self.root, "ACTIVE")
        self.assertTrue(backup.exists())
        self.assertEqual(records[0]["id"], identifier)
        self.assertEqual(records[0]["kind"], "cross-cutting-skill-principle")

    def test_potential_secrets_are_rejected(self) -> None:
        candidate = self.observation()
        candidate["issue"] = "api_key=super-secret-value"
        with self.assertRaisesRegex(governor.GovernorError, "secret"):
            governor.add_observation(self.root, candidate)

    def test_prepare_and_verify_never_modify_live(self) -> None:
        live = self.make_skill()
        before = governor.aggregate_digest(governor.package_manifest(live))
        prepared = governor.prepare_stage(self.root, live, "example-skill")
        stage = Path(prepared["stage_path"])
        (stage / "references" / "rules.md").write_text("improved\n", encoding="utf-8")
        report = governor.verify_stage(self.root, live, stage)
        after = governor.aggregate_digest(governor.package_manifest(live))
        self.assertEqual(before, after)
        self.assertTrue(report["live_unchanged"])
        self.assertEqual(report["status"], "VERIFIED_NOT_INSTALLED")
        self.assertIn("references/rules.md", report["changed_files"])

    def test_missing_stage_reference_is_rejected(self) -> None:
        live = self.make_skill()
        prepared = governor.prepare_stage(self.root, live, "example-skill")
        stage = Path(prepared["stage_path"])
        (stage / "references" / "rules.md").unlink()
        with self.assertRaises(governor.GovernorError):
            governor.verify_stage(self.root, live, stage)

    def test_live_drift_requires_rebase(self) -> None:
        live = self.make_skill()
        prepared = governor.prepare_stage(self.root, live, "example-skill")
        stage = Path(prepared["stage_path"])
        (live / "references" / "rules.md").write_text("new live version\n", encoding="utf-8")
        with self.assertRaisesRegex(governor.GovernorError, "rebase"):
            governor.verify_stage(self.root, live, stage)

    def test_project_memory_kind_is_rejected(self) -> None:
        governor.init_state(self.root)
        store = self.root / "observations" / "observations.json"
        value = json.loads(store.read_text(encoding="utf-8"))
        invalid = self.observation()
        invalid.update(
            {
                "id": "obs-invalid",
                "kind": "project-memory",
                "status": "OPEN",
                "created_at": governor.utc_now(),
            }
        )
        value["observations"].append(invalid)
        governor.atomic_write_json(store, value)
        with self.assertRaisesRegex(governor.GovernorError, "project memory"):
            governor.list_observations(self.root)


if __name__ == "__main__":
    unittest.main()
