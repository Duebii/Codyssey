"""Offline GPT doubles + real HTTP/Firestore adapter logic; never bill OpenAI."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
import httpx
import openai
import pytest

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.openai_client import InvalidModelReply, OpenAIGateway, load_ai_settings
from app.main import create_app
from app.repositories.firestore_conversations import FirestoreConversationRepository
from app.repositories.firestore_records import FirestoreRecordRepository
from app.schemas.conversations import AssistantDraft, ContextPatch, ConversationInput, TurnInput
from app.schemas.plans import ModelReply
from app.services.chat_limits import ChatGuard
from app.services.chat_prompt import MAX_INPUT_BYTES, build_messages, dump
from tests.fake_firestore import FakeFirestore, run_transaction


def answer(**updates):
    result = {"reply_type": "advice", "content": "가상 기록을 참고해 먼저 결과물의 범위를 정해 보세요.",
              "questions": [], "context_update": {"goal": None, "available_minutes": None, "tasks": None, "constraints": None}, "plan": None}
    result.update(updates)
    return result


def plan_reply():
    return answer(reply_type="plan", content="틀린 자유 텍스트: 9999분 쓰세요", plan={
        "available_minutes": 60, "tasks": [{"task_id": "t1", "priority": 1, "reason": "먼저 준비가 필요합니다.",
        "completion_criteria": "자료 목록 저장", "steps": [{"action": "자료 모으기", "minutes": 20}],
        "first_action": "자료 폴더 열기", "checkpoint": "20분 뒤 목록 확인", "fallback": "핵심 자료만 남기기"},
        {"task_id": "t2", "priority": 2, "reason": "준비한 자료로 작성합니다.", "completion_criteria": "초안 저장",
         "steps": [{"action": "초안 쓰기", "minutes": 30}], "first_action": "목차 쓰기",
         "checkpoint": "30분 뒤 초안 확인", "fallback": "문장 교정 미루기"}],
        "buffer_minutes": 10, "deferred": [], "assumptions": ["소요 시간은 추정입니다."]})


CONTEXT = {"available_minutes": 60, "tasks": [{"id": "t1", "title": "자료 준비"},
           {"id": "t2", "title": "지원서 작성", "depends_on": ["t1"]}]}


class FakeAI:
    def __init__(self):
        self.results = []
        self.requests = []

    def generate(self, messages):
        self.requests.append(deepcopy(messages))
        result = self.results.pop(0) if self.results else answer()
        if isinstance(result, Exception):
            raise result
        if callable(result):
            result = result()
        return ModelReply.model_validate(result)


@pytest.fixture
def rig():
    database = FakeFirestore()
    database.data = {"data": {"seed": {"id": "seed", "date": "2026-10-20", "value": 40,
        "estimated_minutes": 30, "task_name": "자료 취합", "category": "프리랜서",
        "memo": "PRIVATE-RAW-MEMO", "source": "synthetic", "created_at": "2026-10-20T00:00:00Z", "updated_at": "2026-10-20T00:00:00Z"}},
        "metadata": {"synthetic": {"data_revision": 1, "summary_stale": True}}}
    records = FirestoreRecordRepository(client_provider=lambda: database, transaction_runner=run_transaction)
    conversations = FirestoreConversationRepository(client_provider=lambda: database, transaction_runner=run_transaction)
    gateway = FakeAI()
    app = create_app(Settings(), records, conversations, gateway)
    with TestClient(app) as client:
        yield SimpleNamespace(db=database, ai=gateway, app=app, manager=app.app.state.manager, client=client)


def post(rig, **kwargs):
    return rig.client.post("/api/chat", json={"message": "무엇부터 할까요?", **kwargs})


def fixed_turn():
    return TurnInput(user_content="이전 질문", assistant=AssistantDraft(content="이전 고정 답변", reply_type="advice",
        evidence={"source": "synthetic", "period": None, "as_of": None, "count": 0, "data_revision": 0}))


def test_chat_injects_summary_in_system_and_atomically_saves_both_messages(rig):
    result = post(rig)
    assert result.status_code == 200
    body = result.json()
    assert set(body) == {"conversation_id", "message", "context"}
    assert "시연용 가상 기록" in body["message"]["content"]
    assert body["message"]["evidence"]["count"] == 1
    assert body["message"]["evidence"]["data_revision"] == 1
    saved = rig.client.get(f"/api/conversations/{body['conversation_id']}").json()["conversation"]
    assert saved["revision"] == 1 and [item["role"] for item in saved["messages"]] == ["user", "assistant"]
    assert saved["messages"][-1] == body["message"] and saved["context"] == body["context"]
    assert saved["title"] == "무엇부터 할까요?"
    messages = rig.ai.requests[0]
    assert messages[0]["role"] == "system" and "RECORD_SUMMARY=" in messages[0]["content"]
    assert '"count":1' in messages[0]["content"] and "PRIVATE-RAW-MEMO" not in dump(messages)
    assert "daily" not in messages[0]["content"] and len(rig.ai.requests) == 1


def test_follow_up_uses_saved_context_mode_and_recent_messages(rig):
    first = post(rig, mode="automation", context={"goal": "반복 작업 줄이기", "available_minutes": 60}).json()
    second = post(rig, conversation_id=first["conversation_id"], message="이어서 설명해 주세요", context={"goal": None}).json()
    assert second["context"]["available_minutes"] == 60 and second["context"]["goal"] is None
    assert second["message"]["mode"] == "automation"
    last = rig.ai.requests[-1]
    assert [message["role"] for message in last] == ["system", "user", "assistant", "user"]
    assert "무엇부터 할까요?" in last[1]["content"]
    saved = rig.manager.conversations.get(first["conversation_id"])["conversation"]
    assert len(saved["messages"]) == 4 and saved["revision"] == 2


def test_latest_summary_service_is_used_on_every_turn(rig):
    first = post(rig).json()
    updated = rig.client.put("/api/data/seed", json={"date": "2026-10-20", "value": 55, "task_name": "자료 취합",
        "category": "프리랜서", "memo": "변경", "estimated_minutes": 30})
    assert updated.status_code == 200
    second = post(rig, conversation_id=first["conversation_id"]).json()
    assert second["message"]["evidence"]["data_revision"] == 2
    assert '"total_minutes":55' in rig.ai.requests[-1][0]["content"]
    old = rig.manager.conversations.get(first["conversation_id"])["conversation"]["messages"][1]
    assert old["evidence"]["data_revision"] == 1


def test_plan_content_is_rendered_from_validated_plan_only(rig):
    rig.ai.results = [plan_reply()]
    response = post(rig, context=CONTEXT)
    assert response.status_code == 200
    message = response.json()["message"]
    assert message["reply_type"] == "plan" and message["plan"]["available_minutes"] == 60
    assert "작업 50분 + 완충 10분 = 60분 / 가능 60분" in message["content"]
    assert "9999" not in message["content"] and "자료 준비" in message["content"]


@pytest.mark.parametrize("change", ["over_budget", "wrong_minutes", "unknown_id", "duplicate", "missing_task", "dependency", "priority", "no_time", "bool_minutes"])
def test_invalid_plans_get_one_repair_then_fail_without_conversation(rig, change):
    invalid = plan_reply()
    plan = invalid["plan"]
    context = deepcopy(CONTEXT)
    if change == "over_budget": plan["buffer_minutes"] = 11
    elif change == "wrong_minutes": plan["available_minutes"] = 59
    elif change == "unknown_id": plan["tasks"][0]["task_id"] = "invented"
    elif change == "duplicate": plan["deferred"] = [{"task_id": "t1", "reason": "중복"}]
    elif change == "missing_task": plan["tasks"].pop()
    elif change == "dependency":
        plan["tasks"].reverse()
        for index, item in enumerate(plan["tasks"], 1): item["priority"] = index
    elif change == "priority": plan["tasks"][0]["priority"] = 2
    elif change == "no_time": context["available_minutes"] = None
    elif change == "bool_minutes": plan["tasks"][0]["steps"][0]["minutes"] = True
    rig.ai.results = [invalid, invalid]
    response = post(rig, context=context)
    assert response.status_code == 502 and response.json()["error"]["code"] == "ai_response_invalid"
    assert len(rig.ai.requests) == 2 and not rig.db.data.get("conversations")


def test_valid_repair_is_saved_once(rig):
    invalid = plan_reply()
    invalid["plan"]["buffer_minutes"] = 11
    rig.ai.results = [invalid, plan_reply()]
    response = post(rig, context=CONTEXT)
    assert response.status_code == 200 and len(rig.ai.requests) == 2
    assert len(rig.db.data["conversations"]) == 1
    assert len(next(iter(rig.db.data["conversations"].values()))["messages"]) == 2


def test_natural_language_explicit_facts_are_validated_and_saved(rig):
    result = answer()
    result["context_update"]["available_minutes"] = {"value": 90, "quote": "1시간 30분"}
    result["context_update"]["tasks"] = {"value": [{"id": "t1", "title": "자료 준비"}], "quote": "자료 준비"}
    rig.ai.results = [result]
    response = post(rig, message="오늘 1시간 30분 가능해요. 자료 준비 해야 해요.")
    assert response.status_code == 200
    assert response.json()["context"]["available_minutes"] == 90
    assert response.json()["context"]["tasks"][0]["title"] == "자료 준비"


def test_repeating_validated_form_values_is_not_a_new_context_change(rig):
    result = plan_reply()
    result["context_update"]["available_minutes"] = {"value": 60, "quote": "폼에서 확인된 60분"}
    rig.ai.results = [result]
    response = post(rig, context=CONTEXT)
    assert response.status_code == 200 and response.json()["context"]["available_minutes"] == 60
    assert len(rig.ai.requests) == 1


def test_context_repair_identifies_field_and_preserves_grounded_time_change(rig, caplog):
    invalid = plan_reply()
    invalid["context_update"]["goal"] = {"value": "UNCONFIRMED-PRIVATE-TEXT", "quote": "60분"}
    valid = plan_reply()
    valid["context_update"]["available_minutes"] = {"value": 60, "quote": "60분"}
    rig.ai.results = [invalid, valid]
    created = rig.manager.conversations.create(ConversationInput(
        context=ContextPatch.model_validate({**CONTEXT, "available_minutes": 120})))["conversation"]
    response = post(rig, conversation_id=created["id"], message="60분으로 줄었어요.")
    assert response.status_code == 200 and response.json()["context"]["available_minutes"] == 60
    repair = rig.ai.requests[1][-2]["content"]
    assert "context_update.goal" in repair
    assert "UNCONFIRMED-PRIVATE-TEXT" not in repair + caplog.text


@pytest.mark.parametrize("kind", ["invented_quote", "wrong_minutes", "form_conflict", "invented_goal", "invented_task", "invented_due_date", "invented_importance"])
def test_unconfirmed_or_conflicting_facts_never_become_saved_context(rig, kind):
    result = answer()
    message = "오늘 60분 가능해요. 자료 준비 해야 해요."
    patch = None
    update = result["context_update"]
    if kind == "invented_quote": update["available_minutes"] = {"value": 90, "quote": "90분"}
    elif kind == "wrong_minutes": update["available_minutes"] = {"value": 90, "quote": "60분"}
    elif kind == "form_conflict":
        patch = {"available_minutes": 120}
        update["available_minutes"] = {"value": 60, "quote": "60분"}
    elif kind == "invented_goal": update["goal"] = {"value": "매출 두 배", "quote": message}
    else:
        task = {"id": "t1", "title": "자료 준비"}
        if kind == "invented_task": task["title"] = "아무 작업"
        elif kind == "invented_due_date": task["due_date"] = "2026-11-25"
        elif kind == "invented_importance": task["importance"] = "high"
        update["tasks"] = {"value": [task], "quote": message}
    rig.ai.results = [result, result]
    response = post(rig, message=message, context=patch)
    assert response.status_code == 502 and not rig.db.data.get("conversations")


def test_clarification_keeps_unknown_conditions_and_has_no_plan(rig):
    rig.ai.results = [answer(reply_type="clarification", content="", questions=["이번에 쓸 수 있는 시간과 할 일을 알려주시겠어요?"])]
    response = post(rig)
    assert response.status_code == 200
    body = response.json()
    assert body["message"]["plan"] is None and body["context"]["available_minutes"] is None
    assert "알려주시겠어요" in body["message"]["content"]


def test_automation_advice_can_include_follow_up_questions_without_losing_them(rig):
    rig.ai.results = [answer(reply_type="automation", content="표준 목차와 고객 정보를 분리해 작은 표본부터 확인해 보세요.",
                             questions=["현재 쓰는 문서 양식이 있나요?"])]
    response = post(rig, mode="automation")
    assert response.status_code == 200 and response.json()["message"]["reply_type"] == "automation"
    assert "확인할 점:" in response.json()["message"]["content"]
    assert "현재 쓰는 문서 양식이 있나요?" in response.json()["message"]["content"]


def test_plan_cannot_hide_follow_up_questions_outside_the_plan_renderer(rig):
    invalid = plan_reply()
    invalid["questions"] = ["추가 질문"]
    rig.ai.results = [invalid, invalid]
    assert post(rig, context=CONTEXT).status_code == 502


def test_preflight_limits_and_missing_id_avoid_paid_calls(rig):
    assert post(rig, conversation_id="missing").status_code == 404
    service = rig.manager.conversations
    item = service.create(ConversationInput())["conversation"]
    for revision in range(50): service.save_turn(item["id"], revision, fixed_turn())
    assert post(rig, conversation_id=item["id"]).status_code == 409
    assert rig.ai.requests == []


def test_storage_read_failure_prevents_model_and_commit_failure_leaves_no_half_turn(rig):
    rig.db.fail_reads = True
    assert post(rig).status_code == 503 and not rig.ai.requests
    rig.db.fail_reads = False
    rig.manager.summaries.get()  # Warm summary before simulating a conversation commit failure.
    def fail_after_generation():
        rig.db.fail_commit = True
        return answer()
    rig.ai.results = [fail_after_generation]
    response = post(rig)
    assert response.status_code == 503 and len(rig.ai.requests) == 1
    assert not rig.db.data.get("conversations")


def test_existing_turn_conflict_does_not_overwrite_other_saved_messages(rig):
    service = rig.manager.conversations
    item = service.create(ConversationInput())["conversation"]
    def concurrent_update():
        service.save_turn(item["id"], 0, fixed_turn())
        return answer()
    rig.ai.results = [concurrent_update]
    assert post(rig, conversation_id=item["id"]).status_code == 409
    saved = service.get(item["id"])["conversation"]
    assert saved["revision"] == 1 and len(saved["messages"]) == 2


@pytest.mark.parametrize("status,code", [(504, "upstream_timeout"), (502, "ai_unavailable"), (503, "ai_unavailable"), (429, "rate_limited")])
def test_upstream_failure_is_not_retried_or_saved(rig, status, code):
    rig.ai.results = [ApiError(status, code, "안전한 오류")]
    response = post(rig)
    assert response.status_code == status and response.json()["error"]["code"] == code
    assert len(rig.ai.requests) == 1 and not rig.db.data.get("conversations")


def test_recent_history_is_bounded_without_deleting_full_stored_history(rig):
    item = rig.manager.conversations.create(ConversationInput())["conversation"]
    for revision in range(8): rig.manager.conversations.save_turn(item["id"], revision, fixed_turn())
    assert post(rig, conversation_id=item["id"]).status_code == 200
    assert len(rig.ai.requests[0]) == 14  # system + 12 history + final user
    assert len(rig.manager.conversations.get(item["id"])["conversation"]["messages"]) == 18
    summary = rig.manager.summaries.get()
    history = [{"role": "user", "content": str(index) + "가" * 3999} for index in range(14)]
    messages = build_messages(summary, {}, "review", "검토", history, [], "2026-10-21")
    assert sum(len(item["content"]) for item in messages[1:-1]) <= 20000
    assert "13" in messages[-2]["content"] and len(dump(messages).encode()) < MAX_INPUT_BYTES


def test_rate_concurrency_and_rolling_call_limits():
    time = [0]
    guard = ChatGuard(clock=lambda: time[0], client_per_minute=1, total_per_minute=2, concurrent=2, daily_model_calls=2)
    with guard.request("one", "id"):
        with pytest.raises(ApiError) as conflict:
            with guard.request("two", "id"): pass
        assert conflict.value.status_code == 409
    with pytest.raises(ApiError) as limited:
        with guard.request("one", None): pass
    assert limited.value.status_code == 429
    guard.charge_model_call(); guard.charge_model_call()
    with pytest.raises(ApiError): guard.charge_model_call()
    time[0] = 86401
    with guard.request("one", None): guard.charge_model_call()
    assert guard.active == 0 and not guard.busy


def test_ai_settings_precedence_missing_key_and_secret_representation(tmp_path):
    path = tmp_path / "ai.env"
    path.write_text("OPENAI_API_KEY=private-file-key\nOPENAI_MODEL=gpt-6-luna", encoding="utf-8")
    settings = load_ai_settings(path, {"OPENAI_API_KEY": "private-env-key"})
    assert settings.api_key.get_secret_value() == "private-env-key" and "private-env-key" not in repr(settings)
    with pytest.raises(ApiError) as missing: load_ai_settings(path, {"OPENAI_API_KEY": ""})
    assert missing.value.status_code == 503
    with pytest.raises(ApiError): load_ai_settings(path, {"OPENAI_TIMEOUT_SECONDS": "999999"})


def test_real_sdk_builds_strict_schema_caps_tokens_and_disables_retention_and_retries(tmp_path):
    requests = []
    def transport(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "resp_test", "object": "response", "created_at": 1,
            "model": "gpt-6-luna", "status": "completed", "output": [{"id": "msg_test", "type": "message",
            "role": "assistant", "status": "completed", "content": [{"type": "output_text",
            "text": json.dumps(answer()), "annotations": []}]}]})
    def factory(**kwargs):
        assert kwargs["max_retries"] == 0 and kwargs["timeout"] == 40
        assert kwargs["base_url"] == "https://api.openai.com/v1"
        return openai.OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    gateway = OpenAIGateway(tmp_path / "absent", {"OPENAI_API_KEY": "private-test-only"}, factory)
    assert gateway.generate([{"role": "user", "content": "테스트"}]).reply_type == "advice"
    body = requests[0]
    assert body["store"] is False and body["max_output_tokens"] == 3000 and body["reasoning"] == {"effort": "none"}
    assert body["text"]["format"]["strict"] is True and body["text"]["format"]["schema"]["additionalProperties"] is False


@pytest.mark.parametrize("status,code", [(401, "ai_unavailable"), (429, "rate_limited"), (500, "ai_unavailable")])
def test_real_sdk_errors_are_safe_and_not_retried(tmp_path, caplog, status, code):
    calls = []
    def transport(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": "SECRET-UPSTREAM-DETAIL", "type": "test_error"}})
    def factory(**kwargs): return openai.OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    gateway = OpenAIGateway(tmp_path / "none", {"OPENAI_API_KEY": "private-test-only"}, factory)
    with pytest.raises(ApiError) as failure: gateway.generate([])
    assert failure.value.code == code and len(calls) == 1
    assert "SECRET-UPSTREAM-DETAIL" not in failure.value.message + caplog.text


def test_sdk_timeout_has_no_automatic_retry(tmp_path, caplog):
    calls = []
    def transport(request):
        calls.append(request)
        raise httpx.ReadTimeout("PRIVATE-TIMEOUT", request=request)
    def factory(**kwargs): return openai.OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    gateway = OpenAIGateway(tmp_path / "none", {"OPENAI_API_KEY": "private-test-only"}, factory)
    with pytest.raises(ApiError) as failure: gateway.generate([])
    assert failure.value.status_code == 504 and len(calls) == 1
    assert "PRIVATE-TIMEOUT" not in failure.value.message + caplog.text


def test_refusal_is_not_a_plan_repair_or_a_saved_message(rig, tmp_path):
    calls = []
    def transport(request):
        calls.append(request)
        return httpx.Response(200, json={"id": "resp_test", "object": "response", "created_at": 1,
            "model": "gpt-6-luna", "status": "completed", "output": [{"id": "msg_test", "type": "message",
            "role": "assistant", "status": "completed", "content": [{"type": "refusal", "refusal": "not provided"}]}]})
    def factory(**kwargs): return openai.OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    rig.manager.counsel.gateway = OpenAIGateway(tmp_path / "none", {"OPENAI_API_KEY": "private-test-only"}, factory)
    response = post(rig)
    assert response.status_code == 502 and len(calls) == 1 and not rig.db.data.get("conversations")


def test_unmentioned_task_facts_are_preserved_or_rejected(rig):
    context = {"tasks": [{"id": "t1", "title": "자료 준비", "due_date": "2026-10-25", "importance": "high"}]}
    first = post(rig, context=context).json()
    result = answer()
    result["context_update"]["tasks"] = {"value": [{"id": "t1", "title": "자료 준비"}], "quote": "자료 준비"}
    rig.ai.results = [result, result]
    response = post(rig, conversation_id=first["conversation_id"], message="자료 준비부터 설명해 주세요")
    assert response.status_code == 502
    saved = rig.manager.conversations.get(first["conversation_id"])["conversation"]
    assert saved["context"]["tasks"][0]["due_date"] == "2026-10-25" and saved["revision"] == 1


def test_http_limits_include_repair_calls_and_ignore_spoofed_forwarded_header(rig):
    rig.manager.counsel.guard = ChatGuard(client_per_minute=1)
    assert post(rig).status_code == 200
    response = rig.client.post("/api/chat", json={"message": "다른 질문"}, headers={"X-Forwarded-For": "different-client"})
    assert response.status_code == 429 and len(rig.ai.requests) == 1
    rig.manager.counsel.guard = ChatGuard(daily_model_calls=1)
    invalid = plan_reply()
    invalid["plan"]["buffer_minutes"] = 11
    rig.ai.results = [invalid]
    assert post(rig, context=CONTEXT).status_code == 429
    assert len(rig.ai.requests) == 2 and len(rig.db.data["conversations"]) == 1


def test_codyssey_profile_selects_course_gateway_without_ambient_url_override(tmp_path):
    settings = load_ai_settings(tmp_path / "none", {"OPENAI_API_KEY": "private-test-only", "AI_PROVIDER": "codyssey",
        "OPENAI_BASE_URL": "https://untrusted.example/v1"})
    assert settings.provider == "codyssey" and settings.base_url == "https://copa.codyssey.kr/v1"
    assert settings.model == "gpt-5-mini" and settings.reasoning_effort == "omit"
    with pytest.raises(ApiError):
        load_ai_settings(tmp_path / "none", {"OPENAI_API_KEY": "private-test-only", "AI_PROVIDER": "unknown"})


def test_codyssey_sdk_uses_chat_completions_and_preserves_structured_output_and_limits(tmp_path):
    requests = []
    def transport(request):
        assert str(request.url) == "https://copa.codyssey.kr/v1/chat/completions"
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "chatcmpl_test", "object": "chat.completion", "created": 1,
            "model": "gpt-5-mini", "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps(answer()), "refusal": None}}]})
    def factory(**kwargs):
        assert kwargs["max_retries"] == 0 and kwargs["timeout"] == 40
        return openai.OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    gateway = OpenAIGateway(tmp_path / "none", {"OPENAI_API_KEY": "private-test-only", "AI_PROVIDER": "codyssey"}, factory)
    assert gateway.generate([{"role": "user", "content": "테스트"}]).reply_type == "advice"
    body = requests[0]
    assert body["model"] == "gpt-5-mini" and body["max_completion_tokens"] == 3000
    assert "store" not in body and "reasoning_effort" not in body and "response_format" not in body
    assert "JSON_SCHEMA=" in body["messages"][0]["content"]
    assert "context_update" in body["messages"][0]["content"]


@pytest.mark.parametrize("finish_reason", ["length", "content_filter"])
def test_codyssey_does_not_accept_truncated_or_filtered_output(tmp_path, finish_reason):
    def transport(request):
        return httpx.Response(200, json={"id": "chatcmpl_test", "object": "chat.completion", "created": 1,
            "model": "gpt-5-mini", "choices": [{"index": 0, "finish_reason": finish_reason,
            "message": {"role": "assistant", "content": json.dumps(answer())}}]})
    def factory(**kwargs): return openai.OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    gateway = OpenAIGateway(tmp_path / "none", {"OPENAI_API_KEY": "private-test-only", "AI_PROVIDER": "codyssey"}, factory)
    with pytest.raises((InvalidModelReply, ApiError)): gateway.generate([])


def test_codyssey_plain_text_is_still_validated_as_json_without_leaking_output(tmp_path, caplog):
    def transport(request):
        return httpx.Response(200, json={"id": "chatcmpl_test", "object": "chat.completion", "created": 1,
            "model": "gpt-5-mini", "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": "PRIVATE-INVALID-MODEL-OUTPUT"}}]})
    def factory(**kwargs): return openai.OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    gateway = OpenAIGateway(tmp_path / "none", {"OPENAI_API_KEY": "private-test-only", "AI_PROVIDER": "codyssey"}, factory)
    with pytest.raises(InvalidModelReply) as failure: gateway.generate([])
    assert failure.value.reason == "json_or_schema"
    assert "PRIVATE-INVALID-MODEL-OUTPUT" not in str(failure.value) + caplog.text
