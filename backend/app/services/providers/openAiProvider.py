"""
EPIC ? OpenAI LLM & Embedding Provider
Implements LLMProvider and EmbeddingProvider protocols using AsyncOpenAI.
Preserves existing production behavior for gpt-4.1 and text-embedding-3-small untouched.
"""
from __future__ import annotations

import logging
from typing import Any
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """Concrete OpenAI adapter satisfying LLMProvider and EmbeddingProvider protocols."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key
        self._model = model
        self._client: AsyncOpenAI | None = None

    def get_client(self) -> AsyncOpenAI | None:
        """Return configured AsyncOpenAI client or None if API key is missing."""
        key = self._api_key or settings.openai_api_key
        if not key:
            return None
        if self._client is None or getattr(self._client, "api_key", None) != key:
            self._client = AsyncOpenAI(
                api_key=key,
                timeout=30.0,
                max_retries=3,
            )
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
        """Execute chat completion using AsyncOpenAI with graceful fallback."""
        client = self.get_client()
        if client is None:
            raise RuntimeError("OpenAI client unavailable (no API key configured)")

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
                response = await client.chat.completions.create(**params)
            except Exception as first_exc:
                if response_format is not None:
                    params["response_format"] = {"type": "json_object"}
                    response = await client.chat.completions.create(**params)
                else:
                    raise first_exc
            return response.choices[0].message.content or "{}"
        except Exception as exc:
            logger.error("OpenAI chat completion failed: %s", exc)
            raise

    # ?? Embedding Provider Implementation ??????????????????????????????????????

    @property
    def dimension(self) -> int:
        """text-embedding-3-small dimension."""
        return 1536

    def get_dimension(self) -> int:
        return self.dimension

    async def embed_text(self, text: str) -> list[float] | None:
        """Generate an embedding vector via OpenAI text-embedding-3-small."""
        client = self.get_client()
        if client is None:
            return None
        try:
            resp = await client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000],
            )
            return resp.data[0].embedding
        except Exception as exc:
            logger.warning("OpenAI embedding failed: %s", exc, exc_info=True)
            return None

    async def embed(self, text: str) -> list[float] | None:
        return await self.embed_text(text)


class OpenAILLMProvider(OpenAIProvider):
    """Explicit alias for LLMProvider usage."""
    pass


class OpenAIEmbeddingProvider(OpenAIProvider):
    """Explicit alias for EmbeddingProvider usage."""
    pass
