"""SkillShelf shared agent runtime."""

from importlib.metadata import PackageNotFoundError, version

from .contracts import OrchestratorResult, SpecialistResult
from .orchestrator import SkillShelfOrchestrator

__all__ = ["OrchestratorResult", "SkillShelfOrchestrator", "SpecialistResult"]
try:
    __version__ = version("skillshelf-agents")
except PackageNotFoundError:
    __version__ = "0.3.0"
