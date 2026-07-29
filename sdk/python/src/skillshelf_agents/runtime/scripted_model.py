from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

from agents import ModelResponse
from agents.models.interface import Model
from agents.usage import Usage
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)


@dataclass(frozen=True)
class ScriptedModelStep:
    kind: Literal["tool_call", "output"]
    name: str | None = None
    arguments: dict[str, Any] | None = None
    output: str | dict[str, Any] | None = None
    input_tokens: int = 5
    output_tokens: int = 5

    @classmethod
    def tool_call(cls, name: str, arguments: dict[str, Any]) -> "ScriptedModelStep":
        return cls(kind="tool_call", name=name, arguments=arguments)

    @classmethod
    def structured_output(cls, output: dict[str, Any]) -> "ScriptedModelStep":
        return cls(kind="output", output=output)


class ScriptedModel(Model):
    """Deterministic Agents SDK model used by operational graph tests."""

    def __init__(self, steps: list[ScriptedModelStep]) -> None:
        self.steps = list(steps)
        self.requests: list[dict[str, Any]] = []

    async def get_response(
        self,
        system_instructions: str | None,
        input: Any,
        model_settings: Any,
        tools: list[Any],
        output_schema: Any,
        handoffs: list[Any],
        tracing: Any,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: Any,
    ) -> ModelResponse:
        del output_schema, handoffs, tracing, previous_response_id, conversation_id, prompt
        if not self.steps:
            raise RuntimeError("scripted model has no remaining response")
        step = self.steps.pop(0)
        self.requests.append(
            {
                "system_instructions": system_instructions,
                "input": input,
                "max_tokens": model_settings.max_tokens,
                "tools": [tool.name for tool in tools],
            }
        )
        response_id = f"response-{uuid.uuid4().hex}"
        output: list[Any]
        if step.kind == "tool_call":
            if not step.name:
                raise ValueError("tool-call step requires a name")
            output = [
                ResponseFunctionToolCall(
                    arguments=json.dumps(step.arguments or {}, sort_keys=True),
                    call_id=f"call-{uuid.uuid4().hex}",
                    name=step.name,
                    type="function_call",
                )
            ]
        else:
            text = (
                json.dumps(step.output, sort_keys=True)
                if isinstance(step.output, dict)
                else str(step.output or "")
            )
            output = [
                ResponseOutputMessage(
                    id=f"message-{uuid.uuid4().hex}",
                    content=[
                        ResponseOutputText(
                            annotations=[],
                            text=text,
                            type="output_text",
                        )
                    ],
                    role="assistant",
                    status="completed",
                    type="message",
                )
            ]
        return ModelResponse(
            output=output,
            usage=Usage(
                requests=1,
                input_tokens=step.input_tokens,
                output_tokens=step.output_tokens,
                total_tokens=step.input_tokens + step.output_tokens,
            ),
            response_id=response_id,
        )

    async def stream_response(
        self,
        system_instructions: str | None,
        input: Any,
        model_settings: Any,
        tools: list[Any],
        output_schema: Any,
        handoffs: list[Any],
        tracing: Any,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: Any,
    ) -> AsyncIterator[Any]:
        del (
            system_instructions,
            input,
            model_settings,
            tools,
            output_schema,
            handoffs,
            tracing,
            previous_response_id,
            conversation_id,
            prompt,
        )
        if False:
            yield None
        raise NotImplementedError("ScriptedModel supports non-streaming operational tests")
