from __future__ import annotations

import os
from typing import Any

import yaml
from agents import Agent, ModelSettings
from openai.types.shared import Reasoning

from .contracts import GovernanceResult, SpecialistResult
from .registry import AgentDefinition, RuntimeRegistry
from .skill_loader import SkillLoader

OUTPUT_TYPES = {"SpecialistResult": SpecialistResult, "GovernanceResult": GovernanceResult}


class AgentFactory:
    def __init__(self, registry: RuntimeRegistry, skill_loader: SkillLoader) -> None:
        self.registry = registry
        self.skill_loader = skill_loader
        self.profiles = yaml.safe_load(
            (registry.root / "agents" / "model-profiles.yml").read_text(encoding="utf-8")
        )

    def model_for(self, profile_name: str, *, max_tokens: int | None = None) -> tuple[str, ModelSettings]:
        profile = self.profiles["profiles"][profile_name]
        model = os.getenv(profile["env"], os.getenv("SKILLSHELF_MODEL", self.profiles["default_model"]))
        settings = ModelSettings(
            reasoning=Reasoning(effort=profile["reasoning"]),
            verbosity=profile["verbosity"],
            include_usage=True,
            max_tokens=max_tokens,
        )
        return model, settings

    def build_specialist(
        self,
        definition: AgentDefinition,
        *,
        tools: list[Any] | None = None,
        mcp_servers: list[Any] | None = None,
    ) -> Agent:
        instruction = self._read_instruction_file(definition.instruction_file)
        delegation = (
            "You are a bounded specialist called by SkillShelfMaster. Complete only the delegated task. "
            "Do not communicate directly with the user. Return the declared structured output. "
            "Keep context_for_master under 800 tokens and write large artifacts to files. "
            f"Allowed capabilities: {', '.join(definition.allowed_capabilities)}. "
            f"Prohibited capabilities: {', '.join(definition.prohibited_capabilities)}. "
            "Never call yourself or the master and never claim completion without evidence."
        )
        model, model_settings = self.model_for(
            definition.model_profile,
            max_tokens=definition.token_budget.output,
        )
        async def lazy_instructions(_context: Any, _agent: Agent) -> str:
            loaded = self.skill_loader.load_skill(definition.skill)
            return "\n\n".join([instruction, "# Required Skill", loaded.content, "# Delegation Contract", delegation])

        return Agent(
            name=definition.display_name,
            handoff_description=definition.tool_description,
            instructions=lazy_instructions,
            model=model,
            model_settings=model_settings,
            tools=tools or [],
            mcp_servers=mcp_servers or [],
            output_type=OUTPUT_TYPES[definition.output_contract],
        )

    def _read_instruction_file(self, relative: str) -> str:
        path = (self.registry.root / relative).resolve()
        if self.registry.root not in path.parents:
            raise ValueError("instruction path escapes repository")
        return path.read_text(encoding="utf-8")
