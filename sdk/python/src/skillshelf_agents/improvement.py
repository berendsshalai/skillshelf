from __future__ import annotations

import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from filelock import FileLock

from .guardrails import validate_write


class ProposalStore:
    def __init__(self, home: Path, root: Path) -> None:
        self.home, self.root = home, root
        self.directory = home / "staged-updates"
        self.directory.mkdir(parents=True, exist_ok=True)

    def stage(self, target_skill: str, proposed_content: str, evidence_ids: list[str]) -> str:
        source = validate_write(self.root / "skills" / target_skill / "SKILL.md", self.root, approved=False)
        if not source.is_file():
            raise FileNotFoundError(target_skill)
        proposal_id = f"proposal-{uuid.uuid4().hex[:12]}"
        destination = self.directory / proposal_id
        destination.mkdir()
        (destination / "SKILL.md").write_text(proposed_content, encoding="utf-8")
        metadata = {"proposal_id": proposal_id, "target_skill": target_skill, "evidence_ids": evidence_ids,
                    "created_at": datetime.now(UTC).isoformat(), "status": "staged", "approval_required": True}
        (destination / "proposal.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return proposal_id

    def list(self) -> list[dict[str, Any]]:
        return [json.loads(path.read_text(encoding="utf-8"))
                for path in self.directory.glob("*/proposal.json")]

    def inspect(self, proposal_id: str) -> dict[str, Any]:
        value: dict[str, Any] = json.loads(
            (self.directory / proposal_id / "proposal.json").read_text(encoding="utf-8")
        )
        return value

    def reject(self, proposal_id: str) -> None:
        self._set_status(proposal_id, "rejected")

    def approve(self, proposal_id: str, *, confirmed: bool, evaluator: Callable[[str], bool]) -> None:
        if not confirmed:
            raise ValueError("proposal approval requires explicit confirmation")
        metadata = self.inspect(proposal_id)
        target = self.root / "skills" / metadata["target_skill"] / "SKILL.md"
        staged = self.directory / proposal_id / "SKILL.md"
        backup = self.home / "backups" / f"{proposal_id}-SKILL.md"
        backup.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self.directory / proposal_id / ".apply.lock")):
            shutil.copy2(target, backup)
            shutil.copy2(staged, target)
            try:
                if not evaluator(metadata["target_skill"]):
                    raise RuntimeError("affected evaluations failed")
            except Exception:
                shutil.copy2(backup, target)
                self._set_status(proposal_id, "rolled-back")
                raise
            self._set_status(proposal_id, "approved")

    def _set_status(self, proposal_id: str, status: str) -> None:
        path = self.directory / proposal_id / "proposal.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = status
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
