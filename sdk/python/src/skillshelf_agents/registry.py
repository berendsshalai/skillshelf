from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from .contracts import GovernanceResult, OrchestratorResult, SpecialistResult

OUTPUT_CONTRACTS = {
    "SpecialistResult": SpecialistResult,
    "GovernanceResult": GovernanceResult,
    "OrchestratorResult": OrchestratorResult,
}
WRITE_CAPABILITIES = {"write_project_files", "write_observation_log", "create_staged_update"}
LEGACY_CAPABILITY_PROVIDERS: dict[str, list[str]] = {
    "search_sources": ["search_sources", "github-read", "skill-registry-read", "web-read"],
    "search_memory_index": ["search_memory_index", "skillshelf-memory"],
    "inspect_memory_timeline": ["inspect_memory_timeline", "skillshelf-memory"],
    "fetch_selected_observations": ["fetch_selected_observations", "skillshelf-memory"],
    "inspect_browser": ["inspect_browser", "browser-read"],
    "capture_screenshots": ["capture_screenshots", "browser-read"],
    "write_observation_log": ["write_observation_log", "filesystem-governance"],
    "create_staged_update": ["create_staged_update", "filesystem-governance"],
    "read_agent_events": ["read_agent_events", "filesystem-governance"],
}


class TokenBudget(BaseModel):
    input: int = Field(gt=0)
    output: int = Field(gt=0)


class CapabilityPolicy(BaseModel):
    id: str = Field(min_length=1)
    required: bool = True
    providers: list[str] = Field(default_factory=list)
    degraded_behavior: Literal["fail", "report"] = "fail"

    @model_validator(mode="after")
    def consistent(self) -> "CapabilityPolicy":
        if self.required and self.degraded_behavior != "fail":
            raise ValueError("required capabilities must use degraded_behavior: fail")
        return self


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
    capability_policy: dict[str, CapabilityPolicy] = Field(default_factory=dict)
    prohibited_capabilities: list[str]
    token_budget: TokenBudget

    @model_validator(mode="before")
    @classmethod
    def migrate_capabilities(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        raw = data.get("capabilities", data.get("allowed_capabilities", []))
        identifiers: list[str] = []
        policies = dict(data.get("capability_policy", {}))
        for item in raw:
            if isinstance(item, str):
                identifiers.append(item)
                continue
            policy = CapabilityPolicy.model_validate(item)
            identifiers.append(policy.id)
            policies[policy.id] = policy.model_dump()
        data["allowed_capabilities"] = identifiers
        data["capability_policy"] = policies
        data.pop("capabilities", None)
        return data

    @model_validator(mode="after")
    def bounded(self) -> "AgentDefinition":
        if "*" in self.allowed_capabilities or "*" in self.allowed_mcp:
            raise ValueError("unrestricted tool surfaces are forbidden")
        if WRITE_CAPABILITIES.intersection(self.allowed_capabilities) and not self.prohibited_capabilities:
            raise ValueError("write capability requires explicit prohibitions")
        unknown = set(self.capability_policy) - set(self.allowed_capabilities)
        if unknown:
            raise ValueError(f"capability policy references undeclared capabilities: {sorted(unknown)}")
        return self

    @property
    def capability_policies(self) -> list[CapabilityPolicy]:
        return [self.capability_policy_for(item) for item in self.allowed_capabilities]

    def capability_policy_for(self, capability: str) -> CapabilityPolicy:
        if capability not in self.allowed_capabilities:
            raise KeyError(capability)
        configured = self.capability_policy.get(capability)
        if configured is not None:
            return configured
        return CapabilityPolicy(
            id=capability,
            required=True,
            providers=LEGACY_CAPABILITY_PROVIDERS.get(capability, [capability]),
            degraded_behavior="fail",
        )


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
