"""Whole user journeys across HTTP, analysis, context injection and persistence.

These tests use the Firestore double and model double; no cloud/API billing.
Live checks and the limits of the doubles are documented in INTEGRATION.md.
"""
from copy import deepcopy
import json

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import ApiError
from app.main import create_app
from app.repositories.firestore_conversations import FirestoreConversationRepository
from app.repositories.firestore_records import FirestoreRecordRepository
from tests.fake_firestore import run_transaction
from tests.test_chat import CONTEXT, FakeAI, answer, plan_reply, rig  # noqa: F401


def injected_summary(request):
    return json.loads(request[0]['content'].split('\nRECORD_SUMMARY=', 1)[1])


def test_record_crud_updates_next_turn_without_rewriting_historical_evidence(rig):
    baseline = rig.client.get('/api/data/summary').json()
    original = rig.client.get('/api/data').json()['items']
    record = {'date': '2026-10-19', 'value': 17, 'task_name': '검증용 자료 정리',
              'category': '취업', 'memo': 'PRIVATE-INTEGRATION-MEMO', 'estimated_minutes': 20}
    created = rig.client.post('/api/data', json=record)
    assert created.status_code == 201 and created.json()['warning'] is None
    record_id = created.json()['item']['id']
    assert rig.client.get('/api/data').json()['total'] == 2
    conversation_id, snapshots, replies = None, [], []
    for action, value, expected_count, expected_total in [('add', 17, 2, 57), ('update', 31, 2, 71), ('delete', None, 1, 40)]:
        if action == 'update':
            response = rig.client.put('/api/data/' + record_id, json={**record, 'value': value})
            assert response.status_code == 200
        elif action == 'delete':
            assert rig.client.delete('/api/data/' + record_id).status_code == 204
        snapshot = rig.client.get('/api/data/summary').json()
        assert (snapshot['summary']['count'], snapshot['summary']['total_minutes']) == (expected_count, expected_total)
        payload = {'message': f'{action} 후 현재 수치를 확인해 주세요.', 'mode': 'review'}
        if conversation_id:
            payload['conversation_id'] = conversation_id
        response = rig.client.post('/api/chat', json=payload)
        assert response.status_code == 200
        result = response.json()
        conversation_id = result['conversation_id']
        assert result['message']['evidence']['count'] == expected_count
        assert result['message']['evidence']['data_revision'] == snapshot['data_revision']
        # Assert what actually reached the model, not just returned metadata.
        assert injected_summary(rig.ai.requests[-1])['data_revision'] == snapshot['data_revision']
        prompt_summary = injected_summary(rig.ai.requests[-1])['summary']
        assert (prompt_summary['count'], prompt_summary['total_minutes']) == (expected_count, expected_total)
        assert 'PRIVATE-INTEGRATION-MEMO' not in json.dumps(rig.ai.requests[-1])
        snapshots.append(snapshot)
        replies.append(result['message'])
    saved = rig.client.get('/api/conversations/' + conversation_id).json()['conversation']
    assert saved['revision'] == 3
    assert [message['role'] for message in saved['messages']] == ['user', 'assistant'] * 3
    assert saved['messages'][1::2] == replies
    assert [row['data_revision'] for row in snapshots] == [baseline['data_revision'] + n for n in (1, 2, 3)]
    assert rig.client.get('/api/data').json()['items'] == original


def test_reloaded_conversation_changes_deadline_and_time_and_keeps_old_plan(rig):
    rig.ai.results = [plan_reply()]
    first = rig.client.post('/api/chat', json={'message': '두 작업의 실행 계획을 만들어 주세요.', 'context': CONTEXT}).json()
    conversation_id = first['conversation_id']
    # New app/client with new repository instances: persisted state, not old service memory.
    records = FirestoreRecordRepository(client_provider=lambda: rig.db, transaction_runner=run_transaction)
    conversations = FirestoreConversationRepository(client_provider=lambda: rig.db, transaction_runner=run_transaction)
    ai = FakeAI()
    adjusted = plan_reply()
    adjusted['plan']['available_minutes'] = 45
    adjusted['plan']['tasks'][0]['steps'][0]['minutes'] = 15
    adjusted['plan']['tasks'][1]['steps'][0]['minutes'] = 25
    adjusted['plan']['buffer_minutes'] = 5
    adjusted['context_update']['available_minutes'] = {'value': 45, 'quote': '45분'}
    ai.results = [adjusted]
    with TestClient(create_app(Settings(), records, conversations, ai)) as reloaded:
        listing = reloaded.get('/api/conversations').json()
        assert listing['items'][0]['id'] == conversation_id
        previous = reloaded.get('/api/conversations/' + conversation_id).json()['conversation']
        assert previous['messages'][1] == first['message']
        tasks = deepcopy(previous['context']['tasks'])
        tasks[1]['due_date'] = '2026-10-27'
        second = reloaded.post('/api/chat', json={'conversation_id': conversation_id,
            'message': '가능 시간이 45분으로 줄었어요. 바꾼 마감에 맞춰 다시 계획해 주세요.',
            'context': {'tasks': tasks}})
        assert second.status_code == 200
        result = second.json()
        assert result['context']['available_minutes'] == 45
        assert result['context']['tasks'][1]['due_date'] == '2026-10-27'
        plan = result['message']['plan']
        assert sum(step['minutes'] for task in plan['tasks'] for step in task['steps']) + plan['buffer_minutes'] == 45
        request_data = json.loads(ai.requests[0][-1]['content'])
        assert request_data['explicit_fields'] == ['tasks']
        assert request_data['USER_CONTEXT']['available_minutes'] == 60
        saved = reloaded.get('/api/conversations/' + conversation_id).json()['conversation']
        assert saved['revision'] == 2 and len(saved['messages']) == 4
        assert saved['messages'][1] == first['message']
        assert saved['messages'][0]['context']['available_minutes'] == 60
        assert saved['messages'][-1]['context']['available_minutes'] == 45


def test_failures_do_not_leave_partial_turns_and_recovery_appends_exactly_one_pair(rig):
    first = rig.client.post('/api/chat', json={'message': '검증용 첫 상담입니다.'}).json()
    conversation_id = first['conversation_id']
    before = rig.client.get('/api/conversations/' + conversation_id).json()
    records_before = rig.client.get('/api/data').json()
    calls_before = len(rig.ai.requests)
    for path, payload, expected in [('/api/chat', {'message': ' ', 'conversation_id': conversation_id}, 422),
                                     ('/api/chat', {'message': '질문', 'conversation_id': 'missing'}, 404),
                                     ('/api/data', {'date': 'invalid', 'value': -1}, 422)]:
        assert rig.client.post(path, json=payload).status_code == expected
    assert len(rig.ai.requests) == calls_before
    rig.ai.results = [ApiError(504, 'upstream_timeout', '상담 응답을 기다리는 시간이 초과됐습니다.')]
    failed = rig.client.post('/api/chat', json={'message': '실패할 상담', 'conversation_id': conversation_id})
    assert failed.status_code == 504
    assert rig.client.get('/api/conversations/' + conversation_id).json() == before
    # Fail persistence after generation; neither message may become visible.
    def fail_after_generation():
        rig.db.fail_commit = True
        return answer()
    rig.ai.results = [fail_after_generation]
    failed = rig.client.post('/api/chat', json={'message': '저장 실패 상담', 'conversation_id': conversation_id})
    rig.db.fail_commit = False
    assert failed.status_code == 503
    assert rig.client.get('/api/conversations/' + conversation_id).json() == before
    recovered = rig.client.post('/api/chat', json={'message': '연결 복구 뒤 새 질문', 'conversation_id': conversation_id})
    assert recovered.status_code == 200
    saved = rig.client.get('/api/conversations/' + conversation_id).json()['conversation']
    assert saved['revision'] == 2 and len(saved['messages']) == 4
    assert saved['messages'][:2] == before['conversation']['messages']
    assert saved['messages'][-2]['content'] == '연결 복구 뒤 새 질문'
    assert rig.client.get('/api/data').json() == records_before
