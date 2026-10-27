from __future__ import annotations

from contextlib import contextmanager
import logging
from typing import Callable

from app.core.errors import ApiError
from app.repositories.records import DailyLimitExceeded, RecordConflict, RecordNotFound, RecordRepository, RepositoryUnavailable
from app.schemas.records import RecordInput


logger = logging.getLogger("kim_manager.summary")


class RecordService:
    def __init__(self, repository: RecordRepository, refresh_summary: Callable | None = None):
        self.repository = repository
        self.refresh_summary = refresh_summary

    def _refresh(self) -> dict | None:
        if self.refresh_summary is None:
            return None
        try:
            self.refresh_summary()
        except Exception as exc:
            logger.warning("Record saved but summary refresh failed (%s)", type(exc).__name__)
            return {"code": "summary_refresh_failed",
                    "message": "작업 기록은 저장했지만 최신 요약을 갱신하지 못했습니다. 요약을 다시 조회해 주세요."}
        return None

    @contextmanager
    def _errors(self):
        try:
            yield
        except RecordNotFound:
            raise ApiError(404, "not_found", "해당 가상 작업 기록을 찾을 수 없습니다.") from None
        except RecordConflict:
            raise ApiError(409, "record_conflict", "같은 ID의 기록이 이미 있거나 출처가 다릅니다. 기존 기록은 덮어쓰지 않았습니다.") from None
        except DailyLimitExceeded:
            raise ApiError(422, "daily_limit_exceeded", "해당 날짜의 작업 시간 합계는 1,440분을 넘을 수 없습니다.", ["date", "value"]) from None
        except RepositoryUnavailable as exc:
            raise ApiError(503, "storage_unavailable", str(exc)) from None

    def list(self, page: int, page_size: int) -> dict:
        with self._errors():
            items = self.repository.list_all()
        start = (page - 1) * page_size
        return {"items": items[start:start + page_size], "total": len(items), "page": page, "page_size": page_size, "source": "synthetic"}

    def create(self, payload: RecordInput) -> dict:
        with self._errors():
            item = self.repository.create(payload.model_dump(mode="json"))
        return {"item": item, "warning": self._refresh()}

    def update(self, record_id: str, payload: RecordInput) -> dict:
        with self._errors():
            item = self.repository.update(record_id, payload.model_dump(mode="json"))
        return {"item": item, "warning": self._refresh()}

    def delete(self, record_id: str) -> None:
        with self._errors():
            self.repository.delete(record_id)
        self._refresh()
