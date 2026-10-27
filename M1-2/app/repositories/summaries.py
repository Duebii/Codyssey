"""Versioned snapshots and summary cache storage contract."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SummaryState:
    revision: int
    stale: bool
    cached: dict | None


@dataclass(frozen=True)
class RecordSnapshot:
    revision: int
    records: list[dict]


class SummaryRepository(Protocol):
    def summary_state(self) -> SummaryState: ...

    def summary_snapshot(self) -> RecordSnapshot: ...

    def save_summary_if_current(self, document: dict) -> bool: ...
