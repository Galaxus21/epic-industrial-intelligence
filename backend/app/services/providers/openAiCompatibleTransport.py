"""
EPIC — ChatModel and EmbeddingModel for any provider that speaks the OpenAI API format.

OpenAI speaks it natively; Ollama serves it at `<base>/v1` ("OpenAI compatibility",
https://docs.ollama.com/api/openai-compatibility, checked 2026-09-24). The provider adapters
(openAiProvider.py, ollamaProvider.py) only configure these classes: base URL, key, model names, whether
`tool_choice` is sent, and how to tell that the provider is available.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

import httpx
from openai import AsyncOpenAI, BadRequestError

from app.services.providers.llmProvider import AssistantTurn, ChatModelError, ToolCall

logger = logging.getLogger(__name__)

JSON_OBJECT_FORMAT: dict[str, str] = {"type": "json_object"}
DEFAULT_SCHEMA_NAME = "Result"
EMBEDDING_INPUT_CHAR_LIMIT = 8000
TOOL_CHOICE_AUTO = "auto"

AvailabilityCheck = Callable[[], Awaitable[bool]]


class OpenAiCompatibleTransport:
    """Sends chat requests for one model through an OpenAI-format client."""

    def __init__(self, client: AsyncOpenAI, modelName: str, *, sendToolChoice: bool) -> None:
        self._client = client
        self._modelName = modelName
        self._sendToolChoice = sendToolChoice

    async def completeJson(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        maxTokens: int,
        schemaName: str | None = None,
        schema: dict[str, Any] | None = None,
    ) -> str:
        if schema is None:
            return await self._completeText(messages, JSON_OBJECT_FORMAT, temperature, maxTokens)
        schemaFormat = {
            "type": "json_schema",
            "json_schema": {"name": schemaName or DEFAULT_SCHEMA_NAME, "schema": schema},
        }
        try:
            return await self._completeText(messages, schemaFormat, temperature, maxTokens)
        except (BadRequestError, ChatModelError) as exc:
            # A model or server that rejects schema-shaped output (400) or answers it with nothing gets one retry
            # in plain JSON mode; the caller validates the reply against the same schema either way. A timeout
            # or connection error is not retried here: it would only double the wait for a slow local model.
            logger.info("Schema output failed on %s (%s); retrying in JSON mode", self._modelName, exc)
            return await self._completeText(messages, JSON_OBJECT_FORMAT, temperature, maxTokens)

    async def completeWithTools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        temperature: float,
        maxTokens: int,
    ) -> AssistantTurn:
        params: dict[str, Any] = {
            "model": self._modelName,
            "messages": messages,
            "tools": tools,
            "temperature": temperature,
            "max_tokens": maxTokens,
        }
        if self._sendToolChoice:
            params["tool_choice"] = TOOL_CHOICE_AUTO
        response = await self._client.chat.completions.create(**params)
        message = _firstMessage(response)
        return AssistantTurn(content=message.content or "", toolCalls=_toolCallsOf(message))

    async def _completeText(
        self,
        messages: list[dict[str, Any]],
        responseFormat: dict[str, Any],
        temperature: float,
        maxTokens: int,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=self._modelName,
            messages=messages,
            response_format=responseFormat,
            temperature=temperature,
            max_tokens=maxTokens,
        )
        content = _firstMessage(response).content
        if not content:
            raise ChatModelError(f"{self._modelName} returned an empty reply")
        return content


class OpenAiCompatibleChatModel:
    """ChatModel over a transport; `transport` is None when the provider is not configured at all."""

    def __init__(
        self,
        modelName: str,
        transport: OpenAiCompatibleTransport | None,
        availabilityCheck: AvailabilityCheck,
        unavailableReason: str,
    ) -> None:
        self._modelName = modelName
        self._transport = transport
        self._availabilityCheck = availabilityCheck
        self._unavailableReason = unavailableReason

    @property
    def modelName(self) -> str:
        return self._modelName

    async def isAvailable(self) -> bool:
        return self._transport is not None and await self._availabilityCheck()

    async def completeJson(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        maxTokens: int,
        schemaName: str | None = None,
        schema: dict[str, Any] | None = None,
    ) -> str:
        return await self._requireTransport().completeJson(
            messages, temperature=temperature, maxTokens=maxTokens, schemaName=schemaName, schema=schema,
        )

    async def completeWithTools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        temperature: float,
        maxTokens: int,
    ) -> AssistantTurn:
        return await self._requireTransport().completeWithTools(
            messages, tools, temperature=temperature, maxTokens=maxTokens,
        )

    def _requireTransport(self) -> OpenAiCompatibleTransport:
        if self._transport is None:
            raise ChatModelError(self._unavailableReason)
        return self._transport


class OpenAiCompatibleEmbeddingModel:
    """EmbeddingModel over an OpenAI-format client; `client` is None when the provider is not configured."""

    def __init__(
        self,
        client: AsyncOpenAI | None,
        modelName: str,
        dimension: int,
        availabilityCheck: AvailabilityCheck,
    ) -> None:
        self._client = client
        self._modelName = modelName
        self._dimension = dimension
        self._availabilityCheck = availabilityCheck

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, text: str) -> list[float] | None:
        if self._client is None or not await self._availabilityCheck():
            return None
        try:
            response = await self._client.embeddings.create(
                model=self._modelName, input=text[:EMBEDDING_INPUT_CHAR_LIMIT],
            )
        except Exception as exc:
            logger.warning("Embedding with %s failed: %s", self._modelName, exc)
            return None
        return self._checkedVector(response)

    def _checkedVector(self, response: Any) -> list[float] | None:
        if not response.data:
            return None
        vector = list(response.data[0].embedding)
        if len(vector) != self._dimension:
            # A wrong-sized vector would corrupt the Qdrant collection, so the reply is rejected.
            logger.error("%s returned %d dimensions, expected %d", self._modelName, len(vector), self._dimension)
            return None
        return vector


def buildOpenAiClient(
    apiKey: str,
    *,
    timeoutSeconds: float,
    maxRetries: int,
    baseUrl: str | None = None,
    httpClient: httpx.AsyncClient | None = None,
) -> AsyncOpenAI:
    """The one place the SDK client is constructed."""
    return AsyncOpenAI(
        api_key=apiKey,
        base_url=baseUrl,
        timeout=timeoutSeconds,
        max_retries=maxRetries,
        http_client=httpClient,
    )


def _firstMessage(response: Any) -> Any:
    if not response.choices:
        raise ChatModelError("The model returned no choices")
    return response.choices[0].message


def _toolCallsOf(message: Any) -> tuple[ToolCall, ...]:
    calls = []
    for call in message.tool_calls or []:
        function = getattr(call, "function", None)
        if function is None:
            continue
        calls.append(ToolCall(callId=call.id, name=function.name, argumentsJson=function.arguments or "{}"))
    return tuple(calls)
