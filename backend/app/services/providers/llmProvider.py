"""
EPIC — Chat and embedding model interface.

Every LLM call in the app goes through `ChatModel` and every embedding through `EmbeddingModel`, so the
concrete provider (OpenAI or a local Ollama server) is chosen by configuration alone. Callers never see a
vendor SDK object.

The model is an untrusted actor: adapters return raw text and callers validate it (Pydantic models,
citation checks) before anything reaches the user or the database.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class ChatModelError(RuntimeError):
    """The provider failed or returned nothing usable; callers treat it like an unavailable model."""


@dataclass(frozen=True)
class ToolCall:
    callId: str
    name: str
    argumentsJson: str


@dataclass(frozen=True)
class AssistantTurn:
    """One assistant reply in a tool-calling loop: either tool calls to run, or final text."""

    content: str
    toolCalls: tuple[ToolCall, ...] = ()

    def asMessage(self) -> dict[str, Any]:
        """The reply in chat-message form, so it can be appended to the conversation history."""
        message: dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.toolCalls:
            message["tool_calls"] = [
                {"id": call.callId, "type": "function",
                 "function": {"name": call.name, "arguments": call.argumentsJson}}
                for call in self.toolCalls
            ]
        return message


@runtime_checkable
class ChatModel(Protocol):
    """A chat model that answers in JSON or calls tools."""

    @property
    def modelName(self) -> str: ...

    async def isAvailable(self) -> bool:
        """True when a request can be sent now (key configured, or local server up with the model pulled)."""
        ...

    async def completeJson(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        maxTokens: int,
        schemaName: str | None = None,
        schema: dict[str, Any] | None = None,
    ) -> str:
        """Return the model's JSON reply as text. With a schema, ask for schema-shaped output first."""
        ...

    async def completeWithTools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        temperature: float,
        maxTokens: int,
    ) -> AssistantTurn:
        """Return the next assistant turn, which may request tool calls."""
        ...


@runtime_checkable
class EmbeddingModel(Protocol):
    """A text embedding model with a fixed vector size."""

    @property
    def dimension(self) -> int: ...

    async def embed(self, text: str) -> list[float] | None:
        """Return the vector, or None when the model is unavailable or answered with the wrong size."""
        ...
