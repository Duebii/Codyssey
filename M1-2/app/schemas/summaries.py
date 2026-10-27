"""Typed analysis output shared by the API, Firestore and later chat context."""
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class SummaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Period(SummaryModel):
    start: str
    end: str
    calendar_days: int = Field(ge=1)


class CategoryStatistics(SummaryModel):
    category: Literal["프리랜서", "취업", "창업"]
    count: int = Field(ge=1)
    total_minutes: int = Field(ge=1)
    share_percent: float = Field(ge=0, le=100)


class DailyStatistics(SummaryModel):
    date: str
    record_count: int = Field(ge=0)
    total_minutes: int | None
    status: Literal["recorded", "unrecorded"]


class WeeklyStatistics(SummaryModel):
    start: str
    end: str
    calendar_days: int = Field(ge=1, le=7)
    is_partial: bool
    record_count: int = Field(ge=0)
    recorded_days: int = Field(ge=0, le=7)
    unrecorded_days: int = Field(ge=0, le=7)
    total_minutes: int | None
    category_minutes: dict[str, int]


class TaskStatistics(SummaryModel):
    task_name: str
    category: Literal["프리랜서", "취업", "창업"]
    count: int = Field(ge=1)
    total_minutes: int = Field(ge=1)
    average_minutes: float
    paired_count: int = Field(ge=0)
    paired_actual_total_minutes: int = Field(ge=0)
    estimated_total_minutes: int | None
    average_overrun_minutes: float | None
    actual_to_estimated_ratio: float | None


class RecentTrend(SummaryModel):
    basis: str
    recent_start: str | None
    recent_end: str | None
    previous_start: str | None
    previous_end: str | None
    recent_record_count: int = Field(ge=0)
    previous_record_count: int = Field(ge=0)
    recent_recorded_days: int = Field(ge=0, le=7)
    previous_recorded_days: int = Field(ge=0, le=7)
    recent_total_minutes: int = Field(ge=0)
    previous_total_minutes: int = Field(ge=0)
    change_percent: float | None
    threshold_percent: int = 5
    direction: Literal["increase", "decrease", "stable", "insufficient_data"]


class DataSummary(SummaryModel):
    source: Literal["synthetic"] = "synthetic"
    description: str
    period: Period | None
    as_of: str | None
    count: int = Field(ge=0)
    recorded_days: int = Field(ge=0)
    unrecorded_days: int = Field(ge=0)
    total_minutes: int = Field(ge=0)
    average_minutes_per_record: float | None
    min_minutes: int | None
    max_minutes: int | None
    average_minutes_per_recorded_day: float | None
    categories: list[CategoryStatistics]
    recent_trend: RecentTrend
    daily: list[DailyStatistics]
    weekly: list[WeeklyStatistics]
    task_statistics: list[TaskStatistics]
    repeat_review_candidates: list[TaskStatistics]
    limitations: list[str]


class SummaryResponse(SummaryModel):
    summary: DataSummary
    data_revision: int = Field(strict=True, ge=0)
    generated_at: AwareDatetime
