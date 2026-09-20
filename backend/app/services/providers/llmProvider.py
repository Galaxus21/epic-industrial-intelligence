"""
EPIC ? LLM & Embedding Provider Port
Defines abstract protocols for swappable LLM completion and embedding providers.
Mirrors typing.Protocol pattern from app.core.authProvider.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol defining swappable LLM completion operations."""

    def get_client(self) -> Any:
        """Return the underlying client instance (or None if unconfigured)."""
        ...

    async def chat_complete(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2500,
        **kwargs: Any,
    ) -> str:
        """Execute chat completion and return the assistant response content string."""
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol defining swappable embedding operations and vector dimensions."""

    @property
    def dimension(self) -> int:
        """Vector dimension produced by this embedding provider."""
        ...

    def get_dimension(self) -> int:
        """Return the vector dimension (method access)."""
        ...

    def get_client(self) -> Any:
        """Return the underlying client instance (or None if unconfigured)."""
        ...

    async def embed_text(self, text: str) -> list[float] | None:
        """Generate an embedding vector for the input text, or None if unavailable."""
        ...

    async def embed(self, text: str) -> list[float] | None:
        """Alias for embed_text."""
        ...
