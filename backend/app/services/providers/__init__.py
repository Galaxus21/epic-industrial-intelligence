"""
EPIC ? LLM & Embedding Providers Package
Provides swappable provider implementations and factories.
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.services.providers.llmProvider import LLMProvider, EmbeddingProvider
from app.services.providers.openAiProvider import (
    OpenAIProvider,
    OpenAILLMProvider,
    OpenAIEmbeddingProvider,
)
from app.services.providers.liteLlmProvider import (
    LiteLLMProvider,
    LiteLLMEmbeddingProvider,
)

__all__ = [
    "LLMProvider",
    "EmbeddingProvider",
    "OpenAIProvider",
    "OpenAILLMProvider",
    "OpenAIEmbeddingProvider",
    "LiteLLMProvider",
    "LiteLLMEmbeddingProvider",
    "get_llm_provider",
    "get_embedding_provider",
]


@lru_cache
def _cached_llm_provider(name: str) -> LLMProvider:
    if name == "openai":
        return OpenAIProvider()
    elif name == "litellm":
        return LiteLLMProvider()
    raise ValueError(f"Unsupported LLM provider: '{name}'")


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    """Factory returning active LLMProvider based on settings or explicit name.
    Raises ValueError on unrecognized provider.
    """
    raw_name = provider_name if provider_name is not None else settings.llm_provider
    name = (raw_name or "").strip().lower()
    return _cached_llm_provider(name)


@lru_cache
def _cached_embedding_provider(name: str) -> EmbeddingProvider:
    if name == "openai":
        return OpenAIEmbeddingProvider()
    elif name == "litellm":
        return LiteLLMEmbeddingProvider()
    raise ValueError(f"Unsupported embedding provider: '{name}'")


def get_embedding_provider(provider_name: str | None = None) -> EmbeddingProvider:
    """Factory returning active EmbeddingProvider based on settings or explicit name.
    Raises ValueError on unrecognized provider.
    """
    raw_name = provider_name if provider_name is not None else settings.embedding_provider
    name = (raw_name or "").strip().lower()
    return _cached_embedding_provider(name)
