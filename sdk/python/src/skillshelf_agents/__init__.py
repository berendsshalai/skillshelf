"""SkillShelf shared agent runtime."""

from .contracts import OrchestratorResult, SpecialistResult
from .orchestrator import SkillShelfOrchestrator

__all__ = ["OrchestratorResult", "SkillShelfOrchestrator", "SpecialistResult"]
__version__ = "0.2.0"
