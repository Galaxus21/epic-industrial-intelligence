"""
EPIC — LLM and embedding providers.

The app talks to `ChatModel` / `EmbeddingModel` (llmProvider.py) obtained from `modelRegistry`, which picks
OpenAI or a local Ollama server from configuration.
"""
from app.services.providers.llmProvider import (
    AssistantTurn,
    ChatModel,
    ChatModelError,
    EmbeddingModel,
    ToolCall,
)

__all__ = ["AssistantTurn", "ChatModel", "ChatModelError", "EmbeddingModel", "ToolCall"]
