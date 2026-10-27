"""CRUD/import tests exercise the real adapter logic against an offline double."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.firebase import FirebaseClientProvider, read_service_account
from app.main import create_app
from app.repositories.firestore_records import FirestoreRecordRepository
from app.repositories.records import RecordConflict, RepositoryUnavailable
from app.services.import_records import import_records, prepare_import
from tests.fake_firestore import FakeFirestore, run_transaction

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def storage():
    client = FakeFirestore()
    repository = FirestoreRecordRepository(client_provider=lambda: client, transaction_runner=run_transaction)
    return client, repository


@pytest.fixture
def client(storage):
    with TestClient(create_app(Settings(), record_repository=storage[1])) as session:
        yield session


@pytest.fixture
def payload():
    return {"date": "2026-10-20", "value": 40, "memo": "시연용", "task_name": "자료 취합", "category": "프리랜서", "estimated_minutes": 30}


def test_crud_cycle_uses_real_adapter_logic(client, payload, storage):
    created = client.post("/api/data", json=payload)
    assert created.status_code == 201
    item = created.json()["item"]
    assert item["source"] == "synthetic" and item["id"] and item["created_at"] == item["updated_at"]
    assert client.get("/api/data").json()["total"] == 1
    updated = client.put(f"/api/data/{item['id']}", json={**payload, "value": 70, "estimated_minutes": None})
    assert updated.status_code == 200
    assert updated.json()["item"]["value"] == 70
    assert updated.json()["item"]["estimated_minutes"] is None
    assert updated.json()["item"]["created_at"] == item["created_at"]
    deleted = client.delete(f"/api/data/{item['id']}")
    assert deleted.status_code == 204 and deleted.content == b""
    assert client.get("/api/data").json()["items"] == []
    metadata = storage[0].data["metadata"]["synthetic"]
    assert metadata["data_revision"] == 3 and metadata["summary_stale"] is False
    assert storage[0].data["summaries"]["synthetic"]["summary"]["count"] == 0


def test_list_order_and_pagination_are_independent(client, payload, storage):
    repository = storage[1]
    repository.create({**payload, "date": "2026-10-19"}, record_id="b")
    repository.create(payload, record_id="c")
    repository.create(payload, record_id="a")
    first = client.get("/api/data?page=1&page_size=2").json()
    assert first["total"] == 3 and [item["id"] for item in first["items"]] == ["a", "c"]
    assert client.get("/api/data?page=2&page_size=2").json()["items"][0]["id"] == "b"
    assert client.get("/api/data?page=10").json()["items"] == []


def test_missing_ids_return_404_once_storage_is_available(client, payload):
    assert client.put("/api/data/missing", json=payload).status_code == 404
    assert client.delete("/api/data/missing").status_code == 404


def test_daily_limit_is_atomic_and_update_excludes_current_record(client, payload, storage):
    first = client.post("/api/data", json={**payload, "value": 1000}).json()["item"]
    before = deepcopy(storage[0].data)
    failure = client.post("/api/data", json={**payload, "value": 500})
    assert failure.status_code == 422 and failure.json()["error"]["code"] == "daily_limit_exceeded"
    assert storage[0].data == before
    assert client.put(f"/api/data/{first['id']}", json={**payload, "value": 1440}).status_code == 200
    assert client.post("/api/data", json={**payload, "value": 1}).status_code == 422


def test_update_moving_dates_checks_destination_total(client, payload, storage):
    first = client.post("/api/data", json={**payload, "date": "2026-10-19", "value": 1000}).json()["item"]
    assert client.post("/api/data", json={**payload, "value": 500}).status_code == 201
    before = deepcopy(storage[0].data)
    assert client.put(f"/api/data/{first['id']}", json={**payload, "value": 1000}).status_code == 422
    assert storage[0].data == before
    assert client.put(f"/api/data/{first['id']}", json={**payload, "value": 400}).status_code == 200


def test_foreign_source_is_not_listed_modified_deleted_or_counted(client, payload, storage):
    storage[0].data["data"] = {"foreign": {**payload, "id": "foreign", "source": "real", "value": 1440}}
    assert client.get("/api/data").json()["total"] == 0
    assert client.put("/api/data/foreign", json=payload).status_code == 404
    assert client.delete("/api/data/foreign").status_code == 404
    assert client.post("/api/data", json=payload).status_code == 201
    assert storage[0].data["data"]["foreign"]["source"] == "real"


def test_storage_failures_are_safe_and_do_not_commit_partial_writes(client, payload, storage, caplog):
    storage[0].fail_commit = True
    response = client.post("/api/data", json=payload)
    assert response.status_code == 503 and storage[0].data == {}
    assert "private-commit-error" not in response.text and "private-commit-error" not in caplog.text
    storage[0].fail_commit = False
    storage[0].fail_reads = True
    response = client.get("/api/data")
    assert response.status_code == 503
    assert "private-sdk-error" not in response.text and "private-sdk-error" not in caplog.text


def test_import_150_is_repeatable_and_preserves_user_edits(storage):
    records = prepare_import(ROOT / "data" / "work_records.json")
    first = import_records(storage[1], records)
    assert first == {"source": "synthetic", "created": 150, "skipped": 0, "total": 150}
    original = storage[0].data["data"]["demo-001"]
    original["memo"] = "시연 중 수정한 메모"
    second = import_records(storage[1], records)
    assert second == {"source": "synthetic", "created": 0, "skipped": 150, "total": 150}
    assert storage[0].data["data"]["demo-001"]["memo"] == "시연 중 수정한 메모"
    assert storage[0].data["metadata"]["synthetic"]["data_revision"] == 150
    assert len(storage[1].list_all()) == 150


def test_import_can_resume_after_partial_success_without_duplicates(storage):
    records = prepare_import(ROOT / "data" / "work_records.json")
    import_records(storage[1], records[:12])
    result = import_records(storage[1], records)
    assert result["created"] == 138 and result["skipped"] == 12
    assert len(storage[1].list_all()) == 150


def test_import_does_not_overwrite_foreign_id_collision(storage, payload):
    storage[0].data["data"] = {"demo-001": {**payload, "source": "real"}}
    with pytest.raises(RecordConflict):
        storage[1].create(payload, record_id="demo-001", skip_existing=True)
    assert storage[0].data["data"]["demo-001"]["source"] == "real"


@pytest.mark.parametrize("change", ["duplicate", "foreign", "invalid_minutes", "daily_total"])
def test_import_rejects_bad_files_before_any_storage_access(tmp_path, change):
    rows = json.loads((ROOT / "data" / "work_records.json").read_text(encoding="utf-8"))
    if change == "duplicate":
        rows[1]["id"] = rows[0]["id"]
    elif change == "foreign":
        rows[0]["source"] = "real"
    elif change == "invalid_minutes":
        rows[0]["value"] = True
    else:
        rows[0]["value"] = 1440
    path = tmp_path / "records.json"
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        prepare_import(path)


def test_default_import_command_is_offline(monkeypatch, capsys):
    from scripts import import_dummy_data

    def no_client():
        raise AssertionError("Dry-run must not construct a Firestore adapter")

    monkeypatch.setattr(import_dummy_data, "FirestoreRecordRepository", no_client)
    monkeypatch.setattr("sys.argv", ["import_dummy_data.py"])
    assert import_dummy_data.main() == 0
    assert '"records": 150' in capsys.readouterr().out


def test_service_account_missing_conflicting_or_invalid_never_echoes_values(tmp_path):
    path = tmp_path / "absent.env"
    for environment in [{}, {"FIREBASE_SERVICE_ACCOUNT_JSON": "private-inline", "FIREBASE_SERVICE_ACCOUNT_PATH": "private-path"}, {"FIREBASE_SERVICE_ACCOUNT_JSON": "{private-broken"}]:
        with pytest.raises(RepositoryUnavailable) as error:
            read_service_account(path, environment)
        assert "private" not in str(error.value)


def test_client_provider_is_lazy_cached_and_uses_project_id(tmp_path, monkeypatch):
    import firebase_admin
    from firebase_admin import credentials, firestore

    values = {"type": "service_account", "project_id": "offline-unit-test", "client_email": "unit@example.invalid", "private_key": "unit-fake-key", "token_uri": "https://oauth2.googleapis.com/token"}
    env = {"FIREBASE_SERVICE_ACCOUNT_JSON": json.dumps(values)}
    calls = []
    fake_client = object()
    monkeypatch.setattr(credentials, "Certificate", lambda info: info)
    monkeypatch.setattr(firebase_admin, "initialize_app", lambda cert, options, name: calls.append(options) or object())
    monkeypatch.setattr(firestore, "client", lambda app: fake_client)
    provider = FirebaseClientProvider(tmp_path / "absent.env", env)
    assert calls == []
    assert provider.get() is fake_client and provider.get() is fake_client
    assert calls == [{"projectId": "offline-unit-test"}]
