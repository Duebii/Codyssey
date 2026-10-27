from __future__ import annotations

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, Field, field_validator

from app.schemas.common import DateInput, InputModel, Minutes


class RecordInput(InputModel):
    date: DateInput
    value: Minutes
    memo: str = Field(max_length=2000)
    task_name: str = Field(min_length=1, max_length=80)
    category: Literal["프리랜서", "취업", "창업"]
    estimated_minutes: Minutes | None = None

    @field_validator("date")
    @classmethod
    def completed_work_only(cls, value):
        if value > datetime.now(ZoneInfo("Asia/Seoul")).date():
            raise ValueError("완료한 작업의 날짜는 오늘 이후일 수 없습니다.")
        return value

    model_config = {
        **InputModel.model_config,
        "json_schema_extra": {
            "examples": [{"date": "2026-10-20", "value": 40, "memo": "시연용 작업 기록",
                          "task_name": "자료 취합", "category": "프리랜서", "estimated_minutes": 30}]
        },
    }


class RecordOutput(RecordInput):
    model_config = {**InputModel.model_config, "json_schema_extra": {}}

    id: str
    source: Literal["synthetic"]
    created_at: AwareDatetime
    updated_at: AwareDatetime


class RecordWarning(BaseModel):
    code: str
    message: str


class RecordResponse(BaseModel):
    item: RecordOutput
    warning: RecordWarning | None = None


class RecordListResponse(BaseModel):
    items: list[RecordOutput]
    total: int
    page: int
    page_size: int
    source: Literal["synthetic"] = "synthetic"
