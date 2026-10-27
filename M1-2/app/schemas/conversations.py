from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from app.schemas.common import DateInput, InputModel, Minutes
from app.schemas.summaries import Period

Mode = Literal["strategy", "automation", "review"]


class TaskInput(InputModel):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=100)
    due_date: DateInput | None = None
    importance: Literal["high", "medium", "low", "unknown"] = "unknown"
    depends_on: list[str] = Field(default_factory=list, max_length=10)


class ContextPatch(InputModel):
    goal: str | None = Field(default=None, max_length=500)
    available_minutes: Minutes | None = None
    tasks: list[TaskInput] = Field(default_factory=list, max_length=10)
    constraints: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def valid_dependencies(self) -> "ContextPatch":
        task_ids = [task.id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("작업 ID가 중복됐습니다.")
        graph = {task.id: task.depends_on for task in self.tasks}
        for task in self.tasks:
            if len(task.depends_on) != len(set(task.depends_on)):
                raise ValueError("선행 작업이 중복됐습니다.")
            if task.id in task.depends_on or any(parent not in graph for parent in task.depends_on):
                raise ValueError("선행 작업 ID를 확인하세요.")
        completed: set[str] = set()
        visiting: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise ValueError("선행 작업에 순환이 있습니다.")
            if task_id in completed:
                return
            visiting.add(task_id)
            for parent in graph[task_id]:
                visit(parent)
            visiting.remove(task_id)
            completed.add(task_id)

        for task_id in graph:
            visit(task_id)
        return self


class ConversationInput(InputModel):
    title: str = Field(default="새 상담", min_length=1, max_length=80)
    mode: Mode = "strategy"
    context: ContextPatch = Field(default_factory=ContextPatch)


Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


class Evidence(InputModel):
    source: Literal["synthetic"]
    period: Period | None
    as_of: DateInput | None
    count: int = Field(strict=True, ge=0)
    data_revision: int = Field(strict=True, ge=0)


class AssistantDraft(InputModel):
    content: str = Field(min_length=1, max_length=60000)
    reply_type: Literal["clarification", "advice", "plan", "automation", "review"]
    plan: dict | None = None
    evidence: Evidence


class UserMessage(InputModel):
    id: Identifier
    role: Literal["user"]
    content: str = Field(min_length=1, max_length=4000)
    created_at: AwareDatetime
    mode: Mode
    context: ContextPatch


class AssistantMessage(AssistantDraft):
    id: Identifier
    role: Literal["assistant"]
    created_at: AwareDatetime
    mode: Mode
    context: ContextPatch


Message = Annotated[UserMessage | AssistantMessage, Field(discriminator="role")]


class TurnInput(InputModel):
    """Internal persistence input. Never exposed as a client-facing route."""
    user_content: str = Field(min_length=1, max_length=4000)
    assistant: AssistantDraft
    mode: Mode | None = None
    context: ContextPatch | None = None


class ConversationDetail(InputModel):
    id: Identifier
    title: str = Field(min_length=1, max_length=80)
    source: Literal["synthetic"]
    created_at: AwareDatetime
    updated_at: AwareDatetime
    mode: Mode
    context: ContextPatch
    revision: int = Field(strict=True, ge=0)
    messages: list[Message] = Field(max_length=100)


class StoredConversation(ConversationDetail):
    schema_version: Literal[1] = 1
    title_is_custom: bool
    message_count: int = Field(strict=True, ge=0, le=100)
    last_message_preview: str = Field(max_length=100)

    @model_validator(mode="after")
    def consistent_messages(self) -> "StoredConversation":
        if self.updated_at < self.created_at or self.message_count != len(self.messages):
            raise ValueError("Conversation metadata does not match messages")
        if len({message.id for message in self.messages}) != len(self.messages) or len(self.messages) % 2:
            raise ValueError("Messages must be complete, uniquely identified pairs")
        for index, message in enumerate(self.messages):
            if message.role != ("user" if index % 2 == 0 else "assistant"):
                raise ValueError("Unsupported message order or role")
        expected_preview = self.messages[-1].content[:100].strip() if self.messages else ""
        if self.last_message_preview != expected_preview:
            raise ValueError("Conversation preview does not match last message")
        return self


class ConversationListItem(InputModel):
    id: Identifier
    title: str = Field(min_length=1, max_length=80)
    updated_at: AwareDatetime
    message_count: int = Field(strict=True, ge=0, le=100)
    last_message_preview: str = Field(max_length=100)


class StoredConversationListItem(ConversationListItem):
    source: Literal["synthetic"]


class ConversationResponse(InputModel):
    conversation: ConversationDetail


class ConversationListResponse(InputModel):
    items: list[ConversationListItem]
    total: int
    page: int
    page_size: int
