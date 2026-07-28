from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_path
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_repository(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "agents" / "registry.yml").is_file() and (candidate / "skills").is_dir():
            return candidate
    raise FileNotFoundError("SkillShelf repository root not found")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SKILLSHELF_", extra="ignore")
    home: Path = user_data_path("skillshelf", "SkillShelf")
    model: str = "gpt-5.6-sol"
    tracing: str = "off"
    trace_include_sensitive: bool = False
    auto_review: bool = False
    max_delegation_depth: int = 2
    soft_token_limit: int = 40000
    hard_token_limit: int = 60000

    def initialise(self) -> None:
        for name in ("usage", "sessions", "events", "staged-updates", "runs", "backups"):
            (self.home / name).mkdir(parents=True, exist_ok=True)
