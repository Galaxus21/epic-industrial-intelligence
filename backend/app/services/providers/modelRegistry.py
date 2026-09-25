"""
EPIC — Chooses the chat and embedding provider. The only place in the app that knows providers exist.

There is no provider setting: OpenAI is used when OPENAI_API_KEY is set, and the local Ollama server otherwise.

The choice depends on configuration only, never on a network check, so the embedding vector size (and with
it the Qdrant collection) cannot flip in the middle of a run. Whether the chosen chat model can answer right
now is a separate question, asked through `getAvailableChatModel`.

Callers go through this module's attributes (`modelRegistry.getChatModel()`), so a test can swap in a fake
model with one monkeypatch.
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.services.providers.llmProvider import ChatModel, EmbeddingModel
from app.services.providers.ollamaProvider import OllamaProbe, buildOllamaChatModel, buildOllamaEmbeddingModel
from app.services.providers.openAiProvider import buildOpenAiChatModel, buildOpenAiEmbeddingModel

OPENAI = "openai"
OLLAMA = "ollama"


def activeProvider() -> str:
    """`openai` when an OpenAI key is configured, otherwise `ollama`."""
    return OPENAI if settings.openai_api_key.strip() else OLLAMA


def getChatModel() -> ChatModel:
    if activeProvider() == OPENAI:
        return _openAiChatModel(settings.openai_api_key, settings.openai_model)
    return _ollamaChatModel(settings.ollama_base_url, settings.ollama_chat_model)


async def getAvailableChatModel() -> ChatModel | None:
    """The configured chat model if it can answer now, else None (callers then take the no-AI path)."""
    model = getChatModel()
    return model if await model.isAvailable() else None


def getEmbeddingModel() -> EmbeddingModel:
    if activeProvider() == OPENAI:
        return _openAiEmbeddingModel(settings.openai_api_key)
    return _ollamaEmbeddingModel(
        settings.ollama_base_url, settings.ollama_embedding_model, settings.ollama_embedding_dimension,
    )


# Cached per configuration value, so a settings change (or a test patching one) gets a fresh model while
# repeated calls reuse one SDK client and one probe.
@lru_cache
def _openAiChatModel(apiKey: str, modelName: str) -> ChatModel:
    return buildOpenAiChatModel(apiKey, modelName)


@lru_cache
def _openAiEmbeddingModel(apiKey: str) -> EmbeddingModel:
    return buildOpenAiEmbeddingModel(apiKey)


@lru_cache
def _ollamaProbe(baseUrl: str) -> OllamaProbe:
    return OllamaProbe(baseUrl)


@lru_cache
def _ollamaChatModel(baseUrl: str, modelName: str) -> ChatModel:
    return buildOllamaChatModel(baseUrl, modelName, _ollamaProbe(baseUrl))


@lru_cache
def _ollamaEmbeddingModel(baseUrl: str, modelName: str, dimension: int) -> EmbeddingModel:
    return buildOllamaEmbeddingModel(baseUrl, modelName, dimension, _ollamaProbe(baseUrl))
