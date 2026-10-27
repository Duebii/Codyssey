from __future__ import annotations

from pydantic import Field

from app.schemas.common import InputModel
from app.schemas.conversations import AssistantMessage, ContextPatch, Mode
from app.schemas.plans import ExecutionPlan


class ChatInput(InputModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    mode: Mode | None = None
    context: ContextPatch | None = None

    model_config = {
        **InputModel.model_config,
        "json_schema_extra": {
            "examples": [{"message": "오늘 120분 동안 무엇부터 어떻게 할까요?", "mode": "strategy",
                          "context": {"available_minutes": 120, "tasks": [
                              {"id": "t1", "title": "지원서 작성", "importance": "high", "depends_on": []}]}}]
        },
    }


class ChatAssistantMessage(AssistantMessage):
    plan: ExecutionPlan | None


class ChatResponse(InputModel):
    conversation_id: str
    message: ChatAssistantMessage
    context: ContextPatch
