"""Calculation boundaries, cache freshness and real adapter transactions, offline."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.core.errors import ApiError
from app.main import create_app
from app.repositories.firestore_records import FirestoreRecordRepository
from app.repositories.records import RepositoryUnavailable
from app.schemas.summaries import SummaryResponse
from app.services.analysis import analyze_records
from app.services.import_records import import_records, prepare_import
from app.services.summaries import SummaryService
from tests.fake_firestore import FakeFirestore, run_transaction

ROOT = Path(__file__).resolve().parents[1]


def row(day="2026-10-20", value=40, estimated=30, name="자료 취합", category="프리랜서"):
    return {"date": day, "value": value, "estimated_minutes": estimated, "task_name": name,
            "category": category, "memo": "시연용: not included in summaries", "source": "synthetic"}


@pytest.fixture
def storage():
    database = FakeFirestore()
    repository = FirestoreRecordRepository(client_provider=lambda: database, transaction_runner=run_transaction)
    return database, repository


def test_full_seed_matches_every_existing_preview_statistic():
    records = json.loads((ROOT / "data/work_records.json").read_text(encoding="utf-8"))
    preview = json.loads((ROOT / "data/summary.preview.json").read_text(encoding="utf-8"))
    result = analyze_records(records)
    for key in ("source", "period", "as_of", "count", "recorded_days", "unrecorded_days", "total_minutes",
                "average_minutes_per_record", "min_minutes", "max_minutes", "average_minutes_per_recorded_day", "categories", "daily"):
        assert result[key] == preview[key], key
    for key in ("recent_trend",):
        assert {field: result[key][field] for field in preview[key]} == preview[key]
    for key in ("weekly", "task_statistics", "repeat_review_candidates"):
        assert len(result[key]) == len(preview[key])
        for expected, actual in zip(preview[key], result[key]):
            assert {field: actual[field] for field in expected} == expected
    SummaryResponse(summary=result, data_revision=153, generated_at=datetime.now(timezone.utc))
    assert "memo" not in json.dumps(result) and "not included" not in json.dumps(result)


def test_empty_and_single_record_have_no_invented_dates_or_trend():
    empty = analyze_records([])
    assert empty["count"] == empty["total_minutes"] == empty["recorded_days"] == empty["unrecorded_days"] == 0
    assert empty["period"] is empty["as_of"] is empty["average_minutes_per_record"] is None
    assert empty["daily"] == empty["weekly"] == empty["task_statistics"] == []
    assert empty["recent_trend"]["direction"] == "insufficient_data"
    single = analyze_records([row(estimated=None)])
    assert single["weekly"][0]["is_partial"] is True
    assert single["average_minutes_per_recorded_day"] == 40
    assert single["recent_trend"]["change_percent"] is None
    assert single["task_statistics"][0]["paired_count"] == 0
    assert single["task_statistics"][0]["estimated_total_minutes"] is None
    assert single["task_statistics"][0]["average_overrun_minutes"] is None


def test_unrecorded_days_and_empty_windows_are_not_zero_work():
    result = analyze_records([row("2026-09-30", 10), row("2026-10-20", 20)])
    assert result["recorded_days"] == 2 and result["unrecorded_days"] == 19
    assert result["average_minutes_per_recorded_day"] == 15
    assert result["daily"][1] == {"date": "2026-10-01", "record_count": 0, "total_minutes": None, "status": "unrecorded"}
    assert result["weekly"][1]["total_minutes"] is None
    assert result["recent_trend"]["previous_record_count"] == 0
    assert result["recent_trend"]["direction"] == "insufficient_data"


def test_partial_week_and_grouping_use_calendar_days_and_category():
    result = analyze_records([row("2026-10-13", 10, name=" 공통 작업 "),
                              row("2026-10-20", 20, name="공통 작업"),
                              row("2026-10-20", 30, name="공통 작업", category="취업")])
    assert [week["calendar_days"] for week in result["weekly"]] == [7, 1]
    assert [week["is_partial"] for week in result["weekly"]] == [False, True]
    assert len(result["task_statistics"]) == 2
    assert sorted(item["count"] for item in result["task_statistics"]) == [1, 2]


def test_missing_estimates_are_excluded_from_both_comparison_sums():
    result = analyze_records([row(value=40, estimated=20), row(value=100, estimated=None), row(value=20, estimated=40)])
    task = result["task_statistics"][0]
    assert task["count"] == 3 and task["total_minutes"] == 160
    assert task["paired_count"] == 2 and task["paired_actual_total_minutes"] == 60
    assert task["estimated_total_minutes"] == 60 and task["average_overrun_minutes"] == 0
    assert task["actual_to_estimated_ratio"] == 1
    assert result["repeat_review_candidates"] == [task]


@pytest.mark.parametrize("previous,recent,direction", [(1999, 2099, "increase"), (2000, 2100, "stable"),
                                                       (2000, 1900, "stable"), (1999, 1899, "decrease")])
def test_trend_uses_unrounded_thresholds(previous, recent, direction):
    records = [row("2026-10-07", 1000), row("2026-10-08", previous - 1000),
               row("2026-10-14", 1000), row("2026-10-20", recent - 1000)]
    trend = analyze_records(records)["recent_trend"]
    assert trend["direction"] == direction
    assert trend["recent_recorded_days"] == trend["previous_recorded_days"] == 2
    assert abs(trend["change_percent"]) == 5


def test_less_than_fourteen_days_remains_insufficient_even_with_two_windows():
    trend = analyze_records([row("2026-10-08"), row("2026-10-20")])["recent_trend"]
    assert trend["previous_record_count"] == trend["recent_record_count"] == 1
    assert trend["direction"] == "insufficient_data" and trend["change_percent"] is None


@pytest.mark.parametrize("records", [[row(category="other")], [row(value=True)], [row(value=1440), row(value=1)],
                                      [row("0001-01-01"), row("2026-10-20")]])
def test_invalid_or_excessive_stored_data_does_not_generate_a_summary(records):
    with pytest.raises(ValueError):
        analyze_records(records)


def test_earliest_valid_date_does_not_underflow():
    assert analyze_records([row("0001-01-01")])["recent_trend"]["direction"] == "insufficient_data"


def test_empty_api_persists_a_real_version_zero_summary(storage):
    database, repository = storage
    with TestClient(create_app(Settings(), record_repository=repository)) as client:
        response = client.get("/api/data/summary")
    assert response.status_code == 200 and response.json()["data_revision"] == 0
    assert response.json()["summary"]["count"] == 0
    assert database.data["metadata"]["synthetic"]["summary_stale"] is False
    assert database.data["summaries"]["synthetic"]["schema_version"] == 1


def test_summary_analyzes_all_records_and_cache_hit_avoids_rescan(storage, monkeypatch):
    database, repository = storage
    import_records(repository, prepare_import(ROOT / "data/work_records.json"))
    service = SummaryService(repository)
    first = service.get()
    assert first["summary"]["count"] == 150 and first["data_revision"] == 150
    before = deepcopy(database.data)
    monkeypatch.setattr(repository, "summary_snapshot", lambda: pytest.fail("Cache hit must not rescan records"))
    assert service.get() == first and database.data == before


def test_api_crud_refreshes_summary_and_deleted_last_record_becomes_empty(storage):
    database, repository = storage
    payload = {key: value for key, value in row().items() if key != "source"}
    with TestClient(create_app(Settings(), record_repository=repository)) as client:
        item = client.post("/api/data", json=payload).json()
        assert item["warning"] is None
        assert client.get("/api/data/summary").json()["summary"]["total_minutes"] == 40
        assert client.put(f"/api/data/{item['item']['id']}", json={**payload, "value": 60}).status_code == 200
        updated = client.get("/api/data/summary").json()
        assert updated["data_revision"] == 2 and updated["summary"]["total_minutes"] == 60
        assert client.delete(f"/api/data/{item['item']['id']}").status_code == 204
        assert client.get("/api/data/summary").json()["summary"]["count"] == 0
    assert database.data["metadata"]["synthetic"]["data_revision"] == 3


@pytest.mark.parametrize("corruption", ["version", "schema", "payload"])
def test_stale_or_corrupt_cache_is_recomputed(storage, corruption):
    database, repository = storage
    repository.create({key: value for key, value in row().items() if key != "source"})
    service = SummaryService(repository)
    service.get()
    cached = database.data["summaries"]["synthetic"]
    if corruption == "version":
        cached["data_revision"] = 0
    elif corruption == "schema":
        cached["schema_version"] = 0
    else:
        cached["summary"]["count"] = "broken"
    assert service.get()["summary"]["count"] == 1
    assert database.data["summaries"]["synthetic"]["schema_version"] == 1


def test_concurrent_mutation_retries_instead_of_publishing_old_revision(storage, monkeypatch):
    database, repository = storage
    payload = {key: value for key, value in row().items() if key != "source"}
    repository.create(payload)
    original_save = repository.save_summary_if_current
    calls = []

    def mutate_then_save(document):
        calls.append(document["data_revision"])
        if len(calls) == 1:
            repository.create({**payload, "value": 5})
        return original_save(document)

    monkeypatch.setattr(repository, "save_summary_if_current", mutate_then_save)
    result = SummaryService(repository).get()
    assert calls == [1, 2] and result["data_revision"] == 2 and result["summary"]["total_minutes"] == 45
    assert database.data["metadata"]["synthetic"]["summary_stale"] is False


def test_continuous_conflicts_fail_after_bounded_attempts(storage, monkeypatch):
    _, repository = storage
    calls = []
    monkeypatch.setattr(repository, "save_summary_if_current", lambda document: calls.append(document) or False)
    with pytest.raises(ApiError) as failure:
        SummaryService(repository).get()
    assert failure.value.status_code == 503 and len(calls) == 3


def test_refresh_failure_returns_warning_without_undoing_successful_crud(storage, monkeypatch, caplog):
    database, repository = storage
    payload = {key: value for key, value in row().items() if key != "source"}
    service = SummaryService(repository)
    service.get()  # Old, valid empty summary must never hide a failed refresh.

    def fail(*_args):
        raise RepositoryUnavailable("private-error-must-not-echo")

    monkeypatch.setattr(repository, "save_summary_if_current", fail)
    with TestClient(create_app(Settings(), record_repository=repository)) as client:
        created = client.post("/api/data", json=payload)
        assert created.status_code == 201
        assert created.json()["warning"]["code"] == "summary_refresh_failed"
        item_id = created.json()["item"]["id"]
        assert client.get("/api/data").json()["total"] == 1
        failed_summary = client.get("/api/data/summary")
        assert failed_summary.status_code == 503
        assert failed_summary.json()["error"]["code"] == "summary_unavailable"
        assert "private-error" not in failed_summary.text
        assert client.put(f"/api/data/{item_id}", json={**payload, "value": 50}).json()["warning"] is not None
        deleted = client.delete(f"/api/data/{item_id}")
        assert deleted.status_code == 204 and not deleted.content
    assert database.data["metadata"]["synthetic"]["data_revision"] == 3
    assert database.data["metadata"]["synthetic"]["summary_stale"] is True
    assert "private-error" not in caplog.text


def test_failed_summary_transaction_never_clears_stale_flag(storage):
    database, repository = storage
    repository.create({key: value for key, value in row().items() if key != "source"})
    document = {"schema_version": 1, **SummaryResponse(summary=analyze_records([row()]), data_revision=1,
                   generated_at=datetime.now(timezone.utc)).model_dump(mode="json")}
    before = deepcopy(database.data)
    database.fail_commit = True
    with pytest.raises(RepositoryUnavailable):
        repository.save_summary_if_current(document)
    assert database.data == before
