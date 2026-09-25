"""
EPIC — Ollama adapter: configures the OpenAI-compatible models for a local Ollama server.

Facts this file relies on (https://docs.ollama.com/api/openai-compatibility and
https://docs.ollama.com/api/tags, checked 2026-09-24):
- The OpenAI-compatible API is served at `<base>/v1`; a local server requires an API key but ignores it.
- `tool_choice` is listed as unsupported, so it is never sent.
- `GET <base>/api/tags` lists the pulled models as `{"models": [{"name": ..., "model": ...}]}`.

Availability means "the server answers and the configured model is pulled", checked at most once per
probe interval, so a stopped server degrades to "AI unavailable" instead of a timeout on every request.
"""
from __future__ import annotations

import logging
import time
from typing import Callable

import httpx

from app.services.providers.llmProvider import ChatModel, EmbeddingModel
from app.services.providers.openAiCompatibleTransport import (
    OpenAiCompatibleChatModel,
    OpenAiCompatibleEmbeddingModel,
    OpenAiCompatibleTransport,
    buildOpenAiClient,
)

logger = logging.getLogger(__name__)

OLLAMA_API_KEY_PLACEHOLDER = "ollama"
OLLAMA_OPENAI_PATH = "/v1"
OLLAMA_TAGS_PATH = "/api/tags"
# Local models on a laptop CPU can take minutes for a long JSON answer.
OLLAMA_REQUEST_TIMEOUT_SECONDS = 180.0
OLLAMA_MAX_RETRIES = 1
OLLAMA_PROBE_INTERVAL_SECONDS = 30.0
OLLAMA_PROBE_TIMEOUT_SECONDS = 3.0
DEFAULT_MODEL_TAG = "latest"


class OllamaProbe:
    """Asks the Ollama server which models are pulled, at most once per probe interval."""

    def __init__(
        self,
        baseUrl: str,
        httpClient: httpx.AsyncClient | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._tagsUrl = baseUrl.rstrip("/") + OLLAMA_TAGS_PATH
        self._httpClient = httpClient
        self._clock = clock
        self._installed: frozenset[str] = frozenset()
        self._checkedAt: float | None = None

    async def hasModel(self, modelName: str) -> bool:
        if self._checkedAt is None or self._clock() - self._checkedAt >= OLLAMA_PROBE_INTERVAL_SECONDS:
            # The time is recorded only once the answer is in: a call arriving while the first check is still in
            # flight must ask too, not read the empty initial set as "model not pulled".
            self._installed = await self._fetchInstalled()
            self._checkedAt = self._clock()
        return withDefaultTag(modelName) in self._installed

    async def _fetchInstalled(self) -> frozenset[str]:
        try:
            if self._httpClient is not None:
                response = await self._httpClient.get(self._tagsUrl, timeout=OLLAMA_PROBE_TIMEOUT_SECONDS)
            else:
                async with httpx.AsyncClient(timeout=OLLAMA_PROBE_TIMEOUT_SECONDS) as client:
                    response = await client.get(self._tagsUrl)
            response.raise_for_status()
            entries = response.json()["models"]
        except Exception as exc:
            logger.info("Ollama not reachable at %s (%s) — AI unavailable", self._tagsUrl, exc)
            return frozenset()
        return frozenset(withDefaultTag(entry.get("name") or entry.get("model") or "") for entry in entries)


def buildOllamaChatModel(
    baseUrl: str,
    modelName: str,
    probe: OllamaProbe,
    httpClient: httpx.AsyncClient | None = None,
) -> ChatModel:
    transport = OpenAiCompatibleTransport(_client(baseUrl, httpClient), modelName, sendToolChoice=False)

    async def modelIsPulled() -> bool:
        return await probe.hasModel(modelName)

    reason = f"Ollama at {baseUrl} is not running or '{modelName}' is not pulled"
    return OpenAiCompatibleChatModel(modelName, transport, modelIsPulled, reason)


def buildOllamaEmbeddingModel(
    baseUrl: str,
    modelName: str,
    dimension: int,
    probe: OllamaProbe,
    httpClient: httpx.AsyncClient | None = None,
) -> EmbeddingModel:
    async def modelIsPulled() -> bool:
        return await probe.hasModel(modelName)

    return OpenAiCompatibleEmbeddingModel(_client(baseUrl, httpClient), modelName, dimension, modelIsPulled)


def withDefaultTag(modelName: str) -> str:
    """`llama3.1` and `llama3.1:latest` name the same model, so both are compared with the tag spelled out."""
    if not modelName or ":" in modelName:
        return modelName
    return f"{modelName}:{DEFAULT_MODEL_TAG}"


def _client(baseUrl: str, httpClient: httpx.AsyncClient | None):
    return buildOpenAiClient(
        OLLAMA_API_KEY_PLACEHOLDER,
        baseUrl=baseUrl.rstrip("/") + OLLAMA_OPENAI_PATH,
        timeoutSeconds=OLLAMA_REQUEST_TIMEOUT_SECONDS,
        maxRetries=OLLAMA_MAX_RETRIES,
        httpClient=httpClient,
    )
