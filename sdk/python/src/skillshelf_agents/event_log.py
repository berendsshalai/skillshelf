from __future__ import annotations

from pathlib import Path

from filelock import FileLock

from .contracts import Observation


class EventLog:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.index = self.directory / "observations.jsonl"

    def append(self, observation: Observation) -> None:
        line = observation.model_dump_json() + "\n"
        with FileLock(str(self.index) + ".lock"):
            with self.index.open("a", encoding="utf-8") as stream:
                stream.write(line)

    def read(self) -> list[Observation]:
        if not self.index.exists():
            return []
        return [Observation.model_validate_json(line) for line in self.index.read_text(encoding="utf-8").splitlines()]
