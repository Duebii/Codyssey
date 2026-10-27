"""Typed model output. Cross-field and user-context checks live in chat_validation."""
from typing import Annotated, Literal

from pydantic import Field

from app.schemas.common import InputModel, Minutes
from app.schemas.conversations import TaskInput

ShortText = Annotated[str, Field(min_length=1, max_length=300)]


class PlanStep(InputModel):
    action: ShortText
    minutes: Minutes


class PlannedTask(InputModel):
    task_id: str
    priority: int = Field(strict=True, ge=1, le=10)
    reason: ShortText
    completion_criteria: ShortText
    steps: list[PlanStep] = Field(min_length=1, max_length=6)
    first_action: ShortText
    checkpoint: ShortText
    fallback: ShortText


class DeferredTask(InputModel):
    task_id: str
    reason: ShortText


class ExecutionPlan(InputModel):
    available_minutes: Minutes
    tasks: list[PlannedTask] = Field(min_length=1, max_length=10)
    buffer_minutes: int = Field(strict=True, ge=0, le=1440)
    deferred: list[DeferredTask] = Field(max_length=10)
    assumptions: list[ShortText] = Field(max_length=6)


class TextFact(InputModel):
    value: str | None
    quote: str = Field(min_length=1, max_length=4000)


class MinutesFact(InputModel):
    value: Minutes | None
    quote: str = Field(min_length=1, max_length=4000)


class TasksFact(InputModel):
    value: list[TaskInput] = Field(max_length=10)
    quote: str = Field(min_length=1, max_length=4000)


class ContextUpdate(InputModel):
    goal: TextFact | None
    available_minutes: MinutesFact | None
    tasks: TasksFact | None
    constraints: TextFact | None


class ModelReply(InputModel):
    reply_type: Literal["clarification", "advice", "plan", "automation", "review"]
    content: str = Field(max_length=3000)
    questions: list[ShortText] = Field(max_length=2)
    context_update: ContextUpdate
    plan: ExecutionPlan | None
