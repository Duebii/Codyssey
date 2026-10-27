from __future__ import annotations

import re
from datetime import date as CalendarDate
from typing import Annotated

from fastapi import Path
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def iso_date(value: object) -> CalendarDate:
    if type(value) is CalendarDate:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("YYYY-MM-DD 날짜가 필요합니다.")
    return CalendarDate.fromisoformat(value)


DateInput = Annotated[CalendarDate, BeforeValidator(iso_date)]
Minutes = Annotated[int, Field(strict=True, ge=1, le=1440)]
DocumentId = Annotated[str, Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


class ErrorDetail(BaseModel):
    code: str
    message: str
    fields: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str
    service: str
    stage: int
    storage: str
    ai: str


class RecordPagination(InputModel):
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 50


class ConversationPagination(InputModel):
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=50)] = 20
