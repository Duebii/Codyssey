"""Step 3: real HTTP validation, safe failures and CORS without external calls."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.core.config import ConfigurationError, Settings, load_settings
from app.core.errors import ApiError
from app.core.firebase import FirebaseClientProvider
from app.main import create_app
from app.repositories.firestore_records import FirestoreRecordRepository
from app.repositories.firestore_conversations import FirestoreConversationRepository
from app.schemas.conversations import ContextPatch


@pytest.fixture
def app(tmp_path):
    provider = FirebaseClientProvider(env_file=tmp_path / "absent.env", environ={})
    return create_app(Settings(), record_repository=FirestoreRecordRepository(client_provider=provider.get),
                      conversation_repository=FirestoreConversationRepository(client_provider=provider.get))


@pytest.fixture
def client(app):
    with TestClient(app) as session:
        yield session


@pytest.fixture
def record():
    return {"date": "2026-10-20", "value": 40, "memo": "시연용", "task_name": "자료 취합", "category": "프리랜서", "estimated_minutes": 30}


def test_boot_without_secret_settings_does_not_initialize_external_clients(tmp_path, monkeypatch):
    import firebase_admin
    import openai

    def must_not_run(*_args, **_kwargs):
        raise AssertionError("External SDK initialization is outside Step 3")

    monkeypatch.setattr(firebase_admin, "initialize_app", must_not_run)
    monkeypatch.setattr(openai, "OpenAI", must_not_run)
    settings = load_settings(tmp_path / "absent.env", {})
    with TestClient(create_app(settings)) as session:
        response = session.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "김실장", "stage": 7, "storage": "not_checked", "ai": "not_checked"}


def test_swagger_and_openapi_document_current_stage(client):
    assert client.get("/docs").status_code == 200
    document = client.get("/openapi.json").json()
    assert document["info"]["version"] == "0.7.0"
    for path in ["/api/health", "/api/data", "/api/data/summary", "/api/data/{id}", "/api/conversations", "/api/conversations/{id}", "/api/chat"]:
        assert path in document["paths"]
    operation = document["paths"]["/api/data"]["post"]
    assert "requestBody" in operation
    assert operation["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith("ErrorResponse")
    assert "503" in operation["responses"] and "201" in operation["responses"]


@pytest.mark.parametrize("key,value", [
    ("value", -1), ("value", 0), ("value", 1441), ("value", "40"), ("value", 1.5), ("value", True),
    ("estimated_minutes", 0), ("estimated_minutes", "30"), ("date", "2026-02-30"),
    ("date", "2026-1-2"), ("date", "2026-10-20T00:00:00Z"), ("date", 1780000000),
    ("task_name", "   "), ("task_name", "a" * 81), ("category", "unknown"), ("memo", "m" * 2001),
])
def test_invalid_records_fail_before_storage(client, record, key, value):
    record[key] = value
    response = client.post("/api/data", json=record)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert key in response.json()["error"]["fields"]


def test_future_completed_record_is_rejected(client, record):
    record["date"] = (datetime.now(ZoneInfo("Asia/Seoul")).date() + timedelta(days=1)).isoformat()
    assert client.post("/api/data", json=record).status_code == 422


def test_server_owned_fields_are_forbidden_and_values_not_echoed(client, record):
    secret = "NEVER-ECHO-SECRET-IN-REQUEST"
    record["source"] = secret
    response = client.post("/api/data", json=record)
    assert response.status_code == 422
    assert secret not in response.text
    assert response.json()["error"]["fields"] == ["source"]


def test_missing_required_fields_and_bad_json_use_same_error_shape(client, record):
    del record["memo"]
    assert client.post("/api/data", json=record).status_code == 422
    response = client.post("/api/data", content=b"{broken", headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert set(response.json()) == {"error"}
    assert "broken" not in response.text


def test_valid_record_reaches_unconnected_storage_without_success(client, record):
    record.update({"memo": "", "estimated_minutes": None})
    response = client.post("/api/data", json=record)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_unavailable"
    assert "저장·수정·삭제되지 않았습니다" in response.json()["error"]["message"]


@pytest.mark.parametrize("method,path,payload", [
    ("get", "/api/data", None), ("delete", "/api/data/demo-001", None),
    ("get", "/api/data/summary", None), ("get", "/api/conversations", None),
    ("post", "/api/conversations", {}), ("get", "/api/conversations/example-id", None),
    ("delete", "/api/conversations/example-id", None), ("post", "/api/chat", {"message": "안녕하세요"}),
])
def test_pending_operations_do_not_pretend_to_succeed(client, method, path, payload):
    response = client.request(method, path, json=payload)
    assert response.status_code == 503
    assert set(response.json()["error"]) == {"code", "message", "fields"}


def test_put_validates_full_replacement(client, record):
    assert client.put("/api/data/demo-001", json=record).status_code == 503
    assert client.put("/api/data/demo-001", json={"value": 50}).status_code == 422


@pytest.mark.parametrize("path", ["/api/data?page=0", "/api/data?page_size=101", "/api/conversations?page_size=51", "/api/data?unknown=1"])
def test_invalid_pagination_and_unknown_query_params(client, path):
    assert client.get(path).status_code == 422


@pytest.mark.parametrize("payload", [
    {"message": " "}, {"message": "m" * 4001}, {"message": "test", "mode": "invalid"},
    {"message": "test", "context": {"available_minutes": True}},
    {"message": "test", "context": {"available_minutes": "120"}},
    {"message": "test", "context": {"available_minutes": 1441}},
    {"message": "test", "context": {"tasks": None}},
    {"message": "test", "role": "system"},
])
def test_chat_validation(client, payload):
    assert client.post("/api/chat", json=payload).status_code == 422


@pytest.mark.parametrize("tasks", [
    [{"id": "t1", "title": "one"}, {"id": "t1", "title": "duplicate"}],
    [{"id": "t1", "title": "one", "depends_on": ["t1"]}],
    [{"id": "t1", "title": "one", "depends_on": ["missing"]}],
    [{"id": "t1", "title": "one", "depends_on": ["t2"]}, {"id": "t2", "title": "two", "depends_on": ["t1"]}],
])
def test_invalid_dependencies_rejected_before_chat(client, tasks):
    response = client.post("/api/chat", json={"message": "순서를 잡아주세요", "context": {"tasks": tasks}})
    assert response.status_code == 422


def test_valid_dependency_order_and_context_clear_semantics(client):
    tasks = [{"id": "t1", "title": "자료 준비"}, {"id": "t2", "title": "작성", "depends_on": ["t1"]}]
    response = client.post("/api/chat", json={"message": "순서를 잡아주세요", "context": {"tasks": tasks, "available_minutes": 120}})
    assert response.status_code == 503
    assert ContextPatch().model_dump(exclude_unset=True) == {}
    assert ContextPatch(available_minutes=None, tasks=[]).model_dump(exclude_unset=True) == {"available_minutes": None, "tasks": []}


def test_unknown_route_and_wrong_method_have_safe_errors(client):
    assert client.get("/api/not-present").json()["error"]["code"] == "not_found"
    response = client.post("/api/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
    assert "allow" in response.headers


def test_known_service_errors_are_serialized_without_traceback(app):
    @app.app.get("/unit-test/missing")
    def missing():
        raise ApiError(404, "not_found", "해당 기록이 없습니다.")

    with TestClient(app) as session:
        response = session.get("/unit-test/missing")
        assert response.status_code == 404
        assert response.json()["error"]["message"] == "해당 기록이 없습니다."


def test_unexpected_failures_do_not_leak_values_and_keep_cors(app, caplog):
    secret = "PRIVATE-ERROR-MATERIAL-DO-NOT-ECHO"

    @app.app.get("/unit-test/fail")
    def fail():
        raise RuntimeError(secret)

    with TestClient(app) as session:
        response = session.get("/unit-test/fail", headers={"Origin": "http://localhost:5500"})
        assert response.status_code == 500
        assert secret not in response.text and secret not in caplog.text
        assert response.headers["access-control-allow-origin"] == "http://localhost:5500"


def test_cors_preflight_and_validation_response(client):
    headers = {"Origin": "http://localhost:5500", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    response = client.options("/api/data", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5500"
    assert client.options("/api/data", headers={**headers, "Origin": "https://other.example"}).status_code == 400
    response = client.post("/api/data", json={}, headers={"Origin": "http://localhost:5500"})
    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == "http://localhost:5500"


def test_startup_settings_precedence_and_sanitized_failures(tmp_path):
    path = tmp_path / ".env"
    path.write_text("API_BASE_URL=http://localhost:8000\nOPENAI_API_KEY=must-not-be-required\n", encoding="utf-8")
    assert load_settings(path, {"API_BASE_URL": "https://api.example.com"}).api_base_url == "https://api.example.com"
    with pytest.raises(ConfigurationError) as error:
        load_settings(path, {"API_BASE_URL": "https://user:SECRET@example.com"})
    assert "SECRET" not in str(error.value) and "must-not-be-required" not in str(error.value)


def test_render_public_url_is_used_when_no_explicit_api_url_exists(tmp_path):
    environment = {'APP_ENV': 'production', 'ALLOWED_ORIGINS': 'https://frontend.example.com',
                   'RENDER_EXTERNAL_URL': 'https://backend.onrender.com'}
    assert load_settings(tmp_path / 'absent.env', environment).api_base_url == environment['RENDER_EXTERNAL_URL']
    environment['API_BASE_URL'] = 'https://custom-api.example.com'
    assert load_settings(tmp_path / 'absent.env', environment).api_base_url == environment['API_BASE_URL']


@pytest.mark.parametrize("environment", [
    {"APP_ENV": "invalid"}, {"ALLOWED_ORIGINS": ""}, {"ALLOWED_ORIGINS": "http://localhost:5500,"},
    {"ALLOWED_ORIGINS": "*"}, {"API_BASE_URL": "http://localhost:8000/api"}, {"APP_ENV": "production"},
])
def test_invalid_startup_configuration_is_not_silently_accepted(tmp_path, environment):
    with pytest.raises(ConfigurationError):
        load_settings(tmp_path / "absent.env", environment)
