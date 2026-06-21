from typing import Literal

from pydantic import BaseModel, Field


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class RunRequest(BaseModel):
    level: int
    question: str
    history: list[ChatHistoryMessage] = Field(default_factory=list)
