"""
EPIC ? LiteLLM Provider Adapter
Implements LLMProvider and EmbeddingProvider protocols using LiteLLM.
Provides multi-provider and local model routing capability (GAP-03).
"""
from __future__ import annotations

import logging
import os
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class _LiteLLMChatCompletions:
    """Duck-typed async completions interface compatible with AsyncOpenAI."""

    async def create(self, **kwargs: Any) -> Any:
        import litellm
        return await litellm.acompletion(**kwargs)


class _LiteLLMClient:
    """Duck-typed client providing .chat.completions interface for backwards compatibility."""

    def __init__(self, timeout: float = 30.0, max_retries: int = 3) -> None:
        self.chat = type("Chat", (), {"completions": _LiteLLMChatCompletions()})()
        self.timeout = timeout
        self.max_retries = max_retries


class LiteLLMProvider:
    """Concrete LiteLLM adapter satisfying LLMProvider and EmbeddingProvider protocols."""

    def __init__(
        self,
        model: str | None = None,
        embedding_model: str | None = None,
        dimension: int | None = None,
    ) -> None:
        self._model = model
        self._embedding_model = embedding_model or os.getenv("LITELLM_EMBEDDING_MODEL", "text-embedding-3-small")
        dim_str = os.getenv("EMBEDDING_DIMENSION", "1536")
        self._dimension = dimension if dimension is not None else int(dim_str)
        self._client: _LiteLLMClient | None = None

    def get_client(self) -> Any:
        """Return duck-typed client interface compatible with AsyncOpenAI callers."""
        if self._client is None:
            self._client = _LiteLLMClient()
        return self._client

    async def chat_complete(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2500,
        **kwargs: Any,
    ) -> str:
        """Execute chat completion via LiteLLM acompletion."""
        import litellm

        target_model = model or self._model or settings.openai_model
        params: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        if response_format is not None:
            params["response_format"] = response_format

        try:
            try:
                response = await litellm.acompletion(**params)
            except Exception as first_exc:
                if response_format is not None:
                    params["response_format"] = {"type": "json_object"}
                    response = await litellm.acompletion(**params)
                else:
                    raise first_exc
            return response.choices[0].message.content or "{}"
        except Exception as exc:
            logger.error("LiteLLM chat completion failed: %s", exc)
            raise

    # ?? Embedding Provider Implementation ??????????????????????????????????????

    @property
    def dimension(self) -> int:
        """Vector dimension for active embedding model."""
        return self._dimension

    def get_dimension(self) -> int:
        return self.dimension

    async def embed_text(self, text: str) -> list[float] | None:
        """Generate an embedding vector via LiteLLM aembedding."""
        try:
            import litellm

            resp = await litellm.aembedding(
                model=self._embedding_model,
                input=[text[:8000]],
            )
            data = getattr(resp, "data", None) or resp.get("data")
            if not data:
                return None
            item = data[0]
            if isinstance(item, dict):
                return item.get("embedding")
            return getattr(item, "embedding", None)
        except Exception as exc:
            logger.warning("LiteLLM embedding failed: %s", exc, exc_info=True)
            return None

    async def embed(self, text: str) -> list[float] | None:
        return await self.embed_text(text)


class LiteLLMEmbeddingProvider(LiteLLMProvider):
    """Explicit alias for LiteLLM embedding provider."""
    pass
