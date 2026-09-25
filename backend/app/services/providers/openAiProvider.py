"""
EPIC — OpenAI adapter: configures the OpenAI-compatible models for api.openai.com.

Available whenever OPENAI_API_KEY is set; no network call is needed to decide that.
"""
from __future__ import annotations

import httpx

from app.services.providers.llmProvider import ChatModel, EmbeddingModel
from app.services.providers.openAiCompatibleTransport import (
    OpenAiCompatibleChatModel,
    OpenAiCompatibleEmbeddingModel,
    OpenAiCompatibleTransport,
    buildOpenAiClient,
)

OPENAI_TIMEOUT_SECONDS = 30.0
OPENAI_MAX_RETRIES = 3
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
# "By default, the length of the embedding vector is 1536 for text-embedding-3-small"
# (https://developers.openai.com/api/docs/guides/embeddings, checked 2026-09-24).
OPENAI_EMBEDDING_DIMENSION = 1536
MISSING_KEY_REASON = "OPENAI_API_KEY is not set"


def buildOpenAiChatModel(apiKey: str, modelName: str, httpClient: httpx.AsyncClient | None = None) -> ChatModel:
    transport = None
    if apiKey:
        client = _client(apiKey, httpClient)
        transport = OpenAiCompatibleTransport(client, modelName, sendToolChoice=True)
    return OpenAiCompatibleChatModel(modelName, transport, _configured, MISSING_KEY_REASON)


def buildOpenAiEmbeddingModel(apiKey: str, httpClient: httpx.AsyncClient | None = None) -> EmbeddingModel:
    client = _client(apiKey, httpClient) if apiKey else None
    return OpenAiCompatibleEmbeddingModel(client, OPENAI_EMBEDDING_MODEL, OPENAI_EMBEDDING_DIMENSION, _configured)


def _client(apiKey: str, httpClient: httpx.AsyncClient | None):
    return buildOpenAiClient(
        apiKey, timeoutSeconds=OPENAI_TIMEOUT_SECONDS, maxRetries=OPENAI_MAX_RETRIES, httpClient=httpClient,
    )


async def _configured() -> bool:
    # A client exists only when a key was given, so reaching this check already means "configured".
    return True
