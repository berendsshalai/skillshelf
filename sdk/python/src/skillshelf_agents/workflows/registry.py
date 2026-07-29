from __future__ import annotations

from .definitions import WorkflowDefinition


class WorkflowRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, WorkflowDefinition] = {}

    def register(self, definition: WorkflowDefinition) -> None:
        existing = self._definitions.get(definition.id)
        if existing is not None and existing.version == definition.version:
            raise ValueError(f"workflow already registered: {definition.id}@{definition.version}")
        self._definitions[definition.id] = definition

    def inspect(self, workflow_id: str) -> WorkflowDefinition:
        try:
            return self._definitions[workflow_id]
        except KeyError as error:
            raise KeyError(f"workflow not registered: {workflow_id}") from error

    def list(self) -> list[WorkflowDefinition]:
        return [self._definitions[key] for key in sorted(self._definitions)]
