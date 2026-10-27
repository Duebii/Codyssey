"""Validate all seed rows before any writes. Importing is explicit and resumable."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import Field

from app.repositories.records import RecordRepository
from app.schemas.records import RecordInput


class ImportRecord(RecordInput):
    id: str = Field(pattern=r"^demo-\d{3}$")
    source: Literal["synthetic"]


def prepare_import(path: Path) -> list[ImportRecord]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("가상 작업 기록 배열이 필요합니다.")
    records = [ImportRecord.model_validate(row) for row in raw]
    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("가져오기 파일에 중복 ID가 있습니다.")
    totals: dict[str, int] = defaultdict(int)
    for record in records:
        totals[record.date.isoformat()] += record.value
    if any(total > 1440 for total in totals.values()):
        raise ValueError("가져오기 파일의 하루 시간 합계가 1,440분을 초과합니다.")
    return records


def import_records(repository: RecordRepository, records: list[ImportRecord]) -> dict:
    created = skipped = 0
    for record in records:
        payload = record.model_dump(mode="json", exclude={"id", "source"})
        item = repository.create(payload, record_id=record.id, skip_existing=True)
        if item is None:
            skipped += 1
        else:
            created += 1
    return {"source": "synthetic", "created": created, "skipped": skipped, "total": len(records)}
