"""SkillShelf shared agent runtime."""

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

from .contracts import OrchestratorResult, SpecialistResult

if TYPE_CHECKING:
    from .orchestrator import SkillShelfOrchestrator

__all__ = ["OrchestratorResult", "SkillShelfOrchestrator", "SpecialistResult"]


def __getattr__(name: str) -> object:
    if name == "SkillShelfOrchestrator":
        from .orchestrator import SkillShelfOrchestrator

        return SkillShelfOrchestrator
    raise AttributeError(name)


try:
    __version__ = version("skillshelf-agents")
except PackageNotFoundError:
    __version__ = "0.4.0"
