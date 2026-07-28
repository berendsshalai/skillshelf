from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from .contracts import GovernanceResult, OrchestratorResult, SpecialistResult

OUTPUT_CONTRACTS = {
    "SpecialistResult": SpecialistResult,
    "GovernanceResult": GovernanceResult,
    "OrchestratorResult": OrchestratorResult,
}
WRITE_CAPABILITIES = {"write_project_files", "write_observation_log", "create_staged_update"}


class TokenBudget(BaseModel):
    input: int = Field(gt=0)
    output: int = Field(gt=0)


class MasterDefinition(BaseModel):
    id: str
    display_name: str
    description: str
    instruction_file: str
    model_profile: str
    max_turns: int = Field(gt=0, le=20)
    output_contract: str
    specialist_mode: str


class AgentDefinition(BaseModel):
    id: str
    display_name: str
    skill: str
    skill_path: str
    instruction_file: str
    model_profile: str
    output_contract: str
    max_turns: int = Field(gt=0, le=20)
    tool_name: str
    tool_description: str
    allowed_mcp: list[str]
    allowed_capabilities: list[str]
    prohibited_capabilities: list[str]
    token_budget: TokenBudget

    @model_validator(mode="after")
    def bounded(self) -> "AgentDefinition":
        if "*" in self.allowed_capabilities or "*" in self.allowed_mcp:
            raise ValueError("unrestricted tool surfaces are forbidden")
        if WRITE_CAPABILITIES.intersection(self.allowed_capabilities) and not self.prohibited_capabilities:
            raise ValueError("write capability requires explicit prohibitions")
        return self


class RuntimeRegistry(BaseModel):
    schema_version: int
    master: MasterDefinition
    agents: list[AgentDefinition]
    root: Path = Field(exclude=True)

    @classmethod
    def load(cls, root: Path) -> "RuntimeRegistry":
        data = yaml.safe_load((root / "agents" / "registry.yml").read_text(encoding="utf-8"))
        runtime = cls.model_validate({**data, "root": root.resolve()})
        runtime.validate_files_and_policy()
        return runtime

    def validate_files_and_policy(self) -> None:
        if self.schema_version != 1 or len(self.agents) != 5:
            raise ValueError("registry requires schema version 1 and exactly five specialists")
        mcp_data = yaml.safe_load((self.root / "mcp" / "registry.yml").read_text(encoding="utf-8"))
        known = {item["name"] for item in mcp_data["servers"]}
        profiles = yaml.safe_load((self.root / "agents" / "model-profiles.yml").read_text(encoding="utf-8"))
        profile_names = set(profiles["profiles"])
        ids: set[str] = set()
        skills: set[str] = set()
        if self.master.output_contract not in OUTPUT_CONTRACTS:
            raise ValueError(f"unknown output contract: {self.master.output_contract}")
        if self.master.model_profile not in profile_names:
            raise ValueError(f"unknown model profile: {self.master.model_profile}")
        if not (self.root / self.master.instruction_file).is_file():
            raise ValueError(f"missing instruction file: {self.master.instruction_file}")
        for agent in self.agents:
            if agent.id in ids or agent.skill in skills:
                raise ValueError("duplicate agent id or skill")
            ids.add(agent.id)
            skills.add(agent.skill)
            if not (self.root / agent.skill_path).is_file():
                raise ValueError(f"missing skill: {agent.skill_path}")
            if agent.output_contract not in OUTPUT_CONTRACTS:
                raise ValueError(f"unknown output contract: {agent.output_contract}")
            if agent.model_profile not in profile_names:
                raise ValueError(f"unknown model profile: {agent.model_profile}")
            if not (self.root / agent.instruction_file).is_file():
                raise ValueError(f"missing instruction file: {agent.instruction_file}")
            unknown = set(agent.allowed_mcp) - known
            if unknown:
                raise ValueError(f"{agent.id} has unknown MCP identifiers: {sorted(unknown)}")

    def by_id(self, agent_id: str) -> AgentDefinition:
        return next(item for item in self.agents if item.id == agent_id)
