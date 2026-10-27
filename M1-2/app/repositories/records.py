"""Storage contract and storage-independent failure types."""

from typing import Protocol

from app.repositories.summaries import SummaryRepository


class RepositoryUnavailable(Exception):
    """Only safe, application-authored explanations may be stored here."""


class RecordNotFound(Exception):
    pass


class RecordConflict(Exception):
    pass


class DailyLimitExceeded(Exception):
    pass


class RecordRepository(SummaryRepository, Protocol):
    def list_all(self) -> list[dict]: ...

    def create(self, payload: dict, *, record_id: str | None = None, skip_existing: bool = False) -> dict | None: ...

    def update(self, record_id: str, payload: dict) -> dict: ...

    def delete(self, record_id: str) -> None: ...
