"""Conversation APIs and atomic message persistence; no external SDK calls."""
from copy import deepcopy
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.core.errors import ApiError
from app.main import create_app
from app.repositories.firestore_conversations import FirestoreConversationRepository, LIST_FIELDS
from app.repositories.firestore_records import FirestoreRecordRepository
from app.schemas.conversations import AssistantDraft, ContextPatch, ConversationInput, TurnInput
from app.services.conversations import ConversationService
from tests.fake_firestore import FakeFirestore, run_transaction


@pytest.fixture
def storage():
    database = FakeFirestore()
    repository = FirestoreConversationRepository(client_provider=lambda: database, transaction_runner=run_transaction)
    return database, repository, ConversationService(repository)


@pytest.fixture
def client(storage):
    database, repository, _ = storage
    records = FirestoreRecordRepository(client_provider=lambda: database, transaction_runner=run_transaction)
    with TestClient(create_app(Settings(), record_repository=records, conversation_repository=repository)) as session:
        yield session


def turn(question="시연용 질문", answer="시연용 고정 응답: GPT 호출 없음", **kwargs):
    assistant = AssistantDraft(content=answer, reply_type="advice", evidence={
        "source": "synthetic", "period": {"start": "2026-08-26", "end": "2026-10-20", "calendar_days": 56},
        "as_of": "2026-10-20", "count": 150, "data_revision": 156,
    })
    return TurnInput(user_content=question, assistant=assistant, **kwargs)


def test_create_list_get_delete_empty_conversation(client, storage):
    created = client.post("/api/conversations", json={})
    assert created.status_code == 201
    item = created.json()["conversation"]
    assert item["title"] == "새 상담" and item["revision"] == 0 and item["messages"] == []
    assert item["created_at"] == item["updated_at"] and item["source"] == "synthetic"
    assert item["context"] == {"goal": None, "available_minutes": None, "tasks": [], "constraints": None}
    assert "title_is_custom" not in item and "schema_version" not in item
    detail = client.get(f"/api/conversations/{item['id']}")
    assert detail.status_code == 200 and detail.json()["conversation"] == item
    listed = client.get("/api/conversations").json()
    assert listed["total"] == 1 and listed["items"][0]["message_count"] == 0
    assert listed["items"][0]["last_message_preview"] == ""
    assert client.delete(f"/api/conversations/{item['id']}").status_code == 204
    assert client.get("/api/conversations").json()["items"] == []
    assert client.get(f"/api/conversations/{item['id']}").status_code == 404
    deleted_again = client.delete(f"/api/conversations/{item['id']}")
    assert deleted_again.status_code == 404
    assert "data" not in storage[0].data and "metadata" not in storage[0].data and "summaries" not in storage[0].data


def test_full_messages_conditions_and_evidence_round_trip_without_model(client, storage):
    database, _, service = storage
    created = client.post("/api/conversations", json={"mode": "automation", "context": {
        "goal": "반복 작업 정리", "available_minutes": 90,
        "tasks": [{"id": "t1", "title": "자료 취합"}], "constraints": "시연용 조건",
    }}).json()["conversation"]
    saved = service.save_turn(created["id"], 0, turn(answer="가" * 130))["conversation"]
    loaded = client.get(f"/api/conversations/{created['id']}").json()["conversation"]
    assert loaded == saved and loaded["created_at"] == created["created_at"] and loaded["revision"] == 1
    assert [message["role"] for message in loaded["messages"]] == ["user", "assistant"]
    assert loaded["messages"][0]["context"] == loaded["messages"][1]["context"] == created["context"]
    assert loaded["messages"][1]["evidence"]["data_revision"] == 156
    assert loaded["messages"][1]["mode"] == "automation"
    item = client.get("/api/conversations").json()["items"][0]
    assert item["message_count"] == 2 and item["last_message_preview"] == "가" * 100
    assert "messages" not in item and "context" not in item and "evidence" not in item
    assert database.query_projections[-1] == ("conversations", LIST_FIELDS)
    assert "messages" not in LIST_FIELDS


def test_context_patches_preserve_omitted_fields_and_clear_explicit_fields(storage):
    _, _, service = storage
    created = service.create(ConversationInput(context=ContextPatch(goal="원래 목표", available_minutes=60,
        tasks=[{"id": "t1", "title": "첫 작업"}], constraints="원래 제약")))["conversation"]
    first = service.save_turn(created["id"], 0, turn(mode="review", context=ContextPatch(goal="새 목표")))["conversation"]
    assert first["context"]["available_minutes"] == 60 and first["context"]["tasks"][0]["id"] == "t1"
    assert first["context"]["goal"] == "새 목표" and first["mode"] == "review"
    second = service.save_turn(created["id"], 1, turn(context=ContextPatch(goal=None, tasks=[])))["conversation"]
    assert second["context"] == {"goal": None, "available_minutes": 60, "tasks": [], "constraints": "원래 제약"}
    third = service.save_turn(created["id"], 2, turn())["conversation"]
    assert third["context"] == second["context"] and third["mode"] == "review"
    assert third["messages"][0]["context"]["goal"] == "새 목표"
    assert third["messages"][2]["context"]["goal"] is None


@pytest.mark.parametrize("title", [None, "사용자 제목", "새 상담"])
def test_automatic_title_only_changes_an_omitted_title_on_first_turn(storage, title):
    _, _, service = storage
    payload = ConversationInput() if title is None else ConversationInput(title=title)
    item = service.create(payload)["conversation"]
    first = service.save_turn(item["id"], 0, turn(question="나" * 70))["conversation"]
    assert first["title"] == ("나" * 40 if title is None else title)
    second = service.save_turn(item["id"], 1, turn(question="다른 질문"))["conversation"]
    assert second["title"] == first["title"]


@pytest.mark.parametrize("payload", [
    {"title": " "}, {"title": "a" * 81}, {"mode": "other"}, {"context": None},
    {"messages": [{"role": "system", "content": "private-request-do-not-echo"}]},
    {"source": "real"}, {"revision": 999}, {"id": "client-picked-id"},
    {"context": {"available_minutes": True}},
    {"context": {"tasks": [{"id": "t1", "title": "작업", "depends_on": ["t1"]}]}},
])
def test_bad_and_server_owned_inputs_fail_before_storage(client, storage, payload):
    response = client.post("/api/conversations", json=payload)
    assert response.status_code == 422 and storage[0].data == {}
    assert "private-request" not in response.text


def test_list_projection_sorting_ties_and_pagination(client, storage):
    database, _, service = storage
    ids = [service.create(ConversationInput(title=title))["conversation"]["id"] for title in ("첫 상담", "두 번째", "최근 상담")]
    ids[:2] = sorted(ids[:2])
    for conversation_id in ids[:2]:
        database.data["conversations"][conversation_id]["updated_at"] = "2026-10-20T00:00:00Z"
    database.data["conversations"][ids[2]]["updated_at"] = "2026-10-21T00:00:00Z"
    first = client.get("/api/conversations?page_size=2").json()
    assert first["total"] == 3 and [item["id"] for item in first["items"]] == [ids[2], ids[0]]
    assert client.get("/api/conversations?page=2&page_size=2").json()["items"][0]["id"] == ids[1]
    assert client.get("/api/conversations?page=10").json()["items"] == []
    assert client.get("/api/conversations?page=0").status_code == 422
    assert client.get("/api/conversations?unknown=1").status_code == 422


def test_foreign_conversations_are_never_exposed_or_deleted(client, storage):
    database, _, service = storage
    item = service.create(ConversationInput())["conversation"]
    foreign = deepcopy(database.data["conversations"][item["id"]])
    foreign.update(source="real", title="private-foreign-title")
    database.data["conversations"]["foreign"] = foreign
    assert client.get("/api/conversations").json()["total"] == 1
    for method in (client.get, client.delete):
        result = method("/api/conversations/foreign")
        assert result.status_code == 404 and "private-foreign" not in result.text
    assert database.data["conversations"]["foreign"] == foreign


def test_stale_turn_is_rejected_without_duplicate_or_lost_messages(storage):
    database, _, service = storage
    item = service.create(ConversationInput())["conversation"]
    service.save_turn(item["id"], 0, turn())
    before = deepcopy(database.data)
    with pytest.raises(ApiError) as failure:
        service.save_turn(item["id"], 0, turn())
    assert failure.value.status_code == 409 and database.data == before


def test_transaction_checks_revision_again_after_an_interleaved_writer(storage, monkeypatch):
    database, repository, service = storage
    item = service.create(ConversationInput())["conversation"]
    other_repo = FirestoreConversationRepository(client_provider=lambda: database, transaction_runner=run_transaction)
    other_service = ConversationService(other_repo)
    original = repository.save_turn

    def interleave(conversation_id, document, expected_revision):
        other_service.save_turn(conversation_id, 0, turn(question="다른 요청"))
        return original(conversation_id, document, expected_revision)

    monkeypatch.setattr(repository, "save_turn", interleave)
    with pytest.raises(ApiError) as failure:
        service.save_turn(item["id"], 0, turn(question="늦게 도착한 요청"))
    assert failure.value.status_code == 409
    loaded = other_service.get(item["id"])["conversation"]
    assert loaded["revision"] == 1 and loaded["messages"][0]["content"] == "다른 요청"


def test_deleted_conversation_is_not_resurrected_by_late_save(storage, monkeypatch):
    _, repository, service = storage
    item = service.create(ConversationInput())["conversation"]
    original = repository.save_turn

    def delete_first(conversation_id, document, expected_revision):
        repository.delete(conversation_id)
        return original(conversation_id, document, expected_revision)

    monkeypatch.setattr(repository, "save_turn", delete_first)
    with pytest.raises(ApiError) as failure:
        service.save_turn(item["id"], 0, turn())
    assert failure.value.status_code == 404
    assert service.list(1, 20)["total"] == 0


def test_one_hundred_message_limit_is_checked_before_the_next_pair(storage):
    database, _, service = storage
    item = service.create(ConversationInput())["conversation"]
    for revision in range(50):
        service.save_turn(item["id"], revision, turn())
    before = deepcopy(database.data)
    with pytest.raises(ApiError) as failure:
        service.save_turn(item["id"], 50, turn())
    assert failure.value.code == "conversation_limit" and failure.value.status_code == 409
    assert database.data == before


def test_total_content_character_limit(storage):
    database, _, service = storage
    item = service.create(ConversationInput())["conversation"]
    service.save_turn(item["id"], 0, turn(question="a", answer="b" * 59999))
    before = deepcopy(database.data)
    with pytest.raises(ApiError) as failure:
        service.save_turn(item["id"], 1, turn())
    assert failure.value.code == "conversation_limit" and database.data == before


def test_document_limit_counts_utf8_bytes_not_characters(storage):
    database, _, service = storage
    item = service.create(ConversationInput())["conversation"]
    large_turn = turn()
    large_turn.assistant.plan = {"notes": "가" * 175000}
    before = deepcopy(database.data)
    with pytest.raises(ApiError) as failure:
        service.save_turn(item["id"], 0, large_turn)
    assert failure.value.status_code == 413 and database.data == before


def test_non_json_plan_is_rejected_without_any_write(storage):
    database, _, service = storage
    item = service.create(ConversationInput())["conversation"]
    invalid = turn()
    invalid.assistant.plan = {"number": float("nan")}
    before = deepcopy(database.data)
    with pytest.raises(ApiError) as failure:
        service.save_turn(item["id"], 0, invalid)
    assert failure.value.status_code == 422 and database.data == before


def test_storage_failure_is_safe_and_atomic_for_both_messages(client, storage, caplog):
    database, _, service = storage
    item = client.post("/api/conversations", json={}).json()["conversation"]
    before = deepcopy(database.data)
    database.fail_commit = True
    with pytest.raises(ApiError) as failure:
        service.save_turn(item["id"], 0, turn())
    assert failure.value.status_code == 503 and database.data == before
    assert client.delete(f"/api/conversations/{item['id']}").status_code == 503
    assert client.post("/api/conversations", json={}).status_code == 503
    assert database.data == before
    database.fail_commit = False
    database.fail_reads = True
    response = client.get("/api/conversations")
    assert response.status_code == 503 and "private-sdk-error" not in response.text
    assert "private-sdk-error" not in caplog.text and "private-commit-error" not in caplog.text


def test_corrupt_stored_message_never_becomes_a_system_instruction(client, storage):
    database, _, service = storage
    item = service.create(ConversationInput())["conversation"]
    service.save_turn(item["id"], 0, turn())
    stored = database.data["conversations"][item["id"]]
    stored["messages"][0]["role"] = "system"
    stored["messages"][0]["content"] = "private-corrupt-material"
    response = client.get(f"/api/conversations/{item['id']}")
    assert response.status_code == 503 and "private-corrupt" not in response.text


def test_id_collision_never_overwrites_an_existing_conversation(storage, monkeypatch):
    database, _, service = storage
    monkeypatch.setattr("app.services.conversations.uuid4", lambda: SimpleNamespace(hex="fixed"))
    item = service.create(ConversationInput(title="기존 제목"))["conversation"]
    before = deepcopy(database.data)
    with pytest.raises(ApiError) as failure:
        service.create(ConversationInput(title="새 제목"))
    assert failure.value.status_code == 409 and database.data == before
    assert service.get(item["id"])["conversation"]["title"] == "기존 제목"
