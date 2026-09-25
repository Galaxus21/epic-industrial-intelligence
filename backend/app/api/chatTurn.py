"""
EPIC — Conversation history as a client may send it: user and assistant turns only, each bounded.

The server trims what reaches a model further (promptSafety.historyForPrompt); these limits only refuse payloads no
real conversation produces, so a client cannot add a system or tool message or send an unbounded history.
"""
from typing import Annotated

from pydantic import BaseModel, Field

from app.services.promptSafety import HistoryRole

MAX_TURN_CHARS = 8000
MAX_HISTORY_TURNS = 40
MAX_MESSAGE_CHARS = 4000


class ChatTurn(BaseModel):
    role: HistoryRole
    content: str = Field(max_length=MAX_TURN_CHARS)


ChatHistory = Annotated[list[ChatTurn], Field(max_length=MAX_HISTORY_TURNS)]


def historyDicts(history: list[ChatTurn]) -> list[dict[str, str]]:
    return [turn.model_dump() for turn in history]
