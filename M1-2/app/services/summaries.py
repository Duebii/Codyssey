"""Reuse matching summaries; compute and publish only a consistent revision."""
from datetime import datetime, timezone
import json
import logging
from threading import Lock

from pydantic import ValidationError

from app.core.errors import ApiError
from app.repositories.summaries import SummaryRepository
from app.schemas.summaries import SummaryResponse
from app.services.analysis import analyze_records

SCHEMA_VERSION = 1
MAX_SUMMARY_BYTES = 900_000
MAX_REFRESH_ATTEMPTS = 3
logger = logging.getLogger("kim_manager.summary")


class SummaryService:
    def __init__(self, repository: SummaryRepository):
        self.repository = repository
        self._lock = Lock()

    @staticmethod
    def _cached(state) -> dict | None:
        cached = state.cached
        if state.stale or not isinstance(cached, dict) or type(cached.get("schema_version")) is not int:
            return None
        if cached["schema_version"] != SCHEMA_VERSION or cached.get("data_revision") != state.revision:
            return None
        try:
            response = SummaryResponse.model_validate({key: value for key, value in cached.items() if key != "schema_version"})
        except ValidationError:
            return None
        return response.model_dump(mode="json")

    def get(self) -> dict:
        try:
            with self._lock:
                for _ in range(MAX_REFRESH_ATTEMPTS):
                    cached = self._cached(self.repository.summary_state())
                    if cached is not None:
                        return cached
                    snapshot = self.repository.summary_snapshot()
                    response = SummaryResponse(summary=analyze_records(snapshot.records),
                                               data_revision=snapshot.revision, generated_at=datetime.now(timezone.utc))
                    body = response.model_dump(mode="json")
                    document = {"schema_version": SCHEMA_VERSION, **body}
                    if len(json.dumps(document, ensure_ascii=False).encode("utf-8")) > MAX_SUMMARY_BYTES:
                        raise ValueError("Summary document exceeds application size limit")
                    if self.repository.save_summary_if_current(document):
                        return body
            raise ApiError(503, "summary_unavailable", "기록이 계속 변경되어 최신 요약을 확정하지 못했습니다. 잠시 후 요약을 다시 조회해 주세요.")
        except ApiError:
            raise
        except Exception as exc:
            logger.error("Summary refresh failed (%s)", type(exc).__name__)
            raise ApiError(503, "summary_unavailable", "최신 데이터 요약을 만들거나 저장하지 못했습니다. 저장소 연결·기록 형식·분석 기간(최대 3,660일)을 확인하고 다시 조회해 주세요.") from None
