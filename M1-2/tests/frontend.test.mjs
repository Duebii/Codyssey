import test from 'node:test';
import assert from 'node:assert/strict';
import { createApi, ApiError, contextPatch, rebaseContextDraft, EMPTY_CONTEXT, validateContext, recordPayload, minutes, number, todayKST, createDraftJournal, hasUnsentDraft } from '../frontend/lib.js';

const clone = v => structuredClone(v);
function memoryStorage() { const values = new Map(); return { getItem: k => values.get(k) ?? null, setItem: (k, v) => values.set(k, v) }; }
const draft = () => ({ question: '  작성 중 💞\n다음 줄  ', mode: 'automation', baseline: clone(EMPTY_CONTEXT), context: { goal: '  목표  ', time: '', constraints: '', tasks: [{ id: 'a', title: '', due_date: null, importance: 'unknown', depends_on: [] }] }, detailsOpen: true, pending: false });
test('a tab reload restores raw drafts and active consultation, including unfinished task names', () => {
  const storage = memoryStorage(), first = createDraftJournal(storage, 'api');
  first.write('conversation:one', draft());
  const restored = createDraftJournal(storage, 'api');
  assert.equal(restored.active, 'conversation:one'); assert.deepEqual(restored.read(), draft());
  const detached = restored.read(); detached.context.tasks[0].title = 'mutation';
  assert.equal(restored.read().context.tasks[0].title, '');
});
test('a discarded tab recovers from browser backup without live tabs overwriting each other', () => {
  const backup = memoryStorage(), originalTab = memoryStorage();
  const original = createDraftJournal(originalTab, 'api', backup); original.write('new:one', draft());
  const second = createDraftJournal(memoryStorage(), 'api', backup);
  assert.deepEqual(second.read(), draft()); second.write('new:two', { ...draft(), question: '다른 탭' });
  assert.equal(createDraftJournal(originalTab, 'api', backup).read().question, draft().question);
  assert.equal(createDraftJournal(undefined, 'api', backup).read().question, '다른 탭');
  const denied = { getItem() { throw Error(); }, setItem() { throw Error(); } };
  const fallback = createDraftJournal(denied, 'api', backup); assert.equal(fallback.read().question, '다른 탭');
  assert.equal(fallback.write('new', draft()), true); assert.equal(fallback.durable, true);
});
test('new consultations and history selection keep other unsent drafts, scoped to the API and browser tab', () => {
  const storage = memoryStorage(), journal = createDraftJournal(storage, 'api');
  journal.write('new:one', draft()); journal.write('conversation:two', { ...draft(), question: '다른 질문' });
  journal.activate('new:one'); assert.equal(journal.entries().length, 2); assert.equal(journal.read().question, draft().question);
  assert.equal(createDraftJournal(storage, 'other-api').read(), null);
  assert.equal(createDraftJournal(memoryStorage(), 'api').read(), null);
});
test('interrupted sends remain drafts after reload, and only confirmed success can remove them', () => {
  const storage = memoryStorage(), journal = createDraftJournal(storage, 'api');
  journal.write('new:one', { ...draft(), pending: true });
  const restored = createDraftJournal(storage, 'api'); assert.equal(restored.read().pending, true);
  restored.remove('new:one'); restored.write('conversation:saved', { ...draft(), question: '', pending: false });
  assert.equal(createDraftJournal(storage, 'api').read().question, ''); assert.equal(restored.read('new:one'), null);
});
test('saved consultation conditions alone are not mislabeled as an unfinished question', () => {
  const item = draft(); item.question = ''; item.context.tasks = []; item.baseline.goal = '목표';
  assert.equal(hasUnsentDraft(item), false);
  item.context.time = '40'; assert.equal(hasUnsentDraft(item), true);
  item.context.time = ''; item.pending = true; assert.equal(hasUnsentDraft(item), true);
});
test('unavailable or corrupt tab storage degrades without crashing or trusting malformed task data', () => {
  const blocked = createDraftJournal({ getItem() { throw Error(); }, setItem() { throw Error(); } }, 'api');
  assert.equal(blocked.available, false); assert.equal(blocked.write('new', draft()), false); assert.deepEqual(blocked.read(), draft());
  const storage = memoryStorage(); storage.setItem('kim-workspace-v1:api', '{broken');
  assert.equal(createDraftJournal(storage, 'api').read(), null);
  storage.setItem('kim-workspace-v1:api', JSON.stringify({ version: 1, active: 'new', drafts: { new: { ...draft(), context: { ...draft().context, tasks: [null] } } } }));
  assert.equal(createDraftJournal(storage, 'api').read(), null);
});
test('unchanged conditions stay omitted, so natural-language time updates are not contradicted', () => {
  const old = { ...clone(EMPTY_CONTEXT), available_minutes: 120 };
  assert.deepEqual(contextPatch(clone(old), old), {});
  assert.deepEqual(contextPatch({ ...old, available_minutes: 60 }, old), { available_minutes: 60 });
});
test('explicit clears are preserved instead of being silently omitted', () => {
  const old = { goal: '초안', available_minutes: 120, tasks: [{ id: 't1' }], constraints: '자료 필요' };
  assert.deepEqual(contextPatch(clone(EMPTY_CONTEXT), old), EMPTY_CONTEXT);
});
test('conflict recovery preserves edited conditions while adopting newer unedited server values', () => {
  const baseline = { ...clone(EMPTY_CONTEXT), available_minutes: 120, goal: '이전 목표' };
  const draft = { ...baseline, goal: '작성 중인 목표', tasks: [{ id: 'local', title: '초안', depends_on: [] }] };
  const latest = { ...baseline, available_minutes: 90, constraints: '서버의 최신 조건' };
  const rebased = rebaseContextDraft(latest, contextPatch(draft, baseline));
  assert.equal(rebased.goal, draft.goal); assert.deepEqual(rebased.tasks, draft.tasks);
  assert.equal(rebased.available_minutes, 90); assert.equal(rebased.constraints, '서버의 최신 조건');
  assert.deepEqual(contextPatch(rebased, latest), { goal: draft.goal, tasks: draft.tasks });
});
test('conflict recovery retains explicit null and empty tasks instead of restoring cleared fields', () => {
  const latest = { goal: '서버 목표', available_minutes: 90, constraints: '서버 조건', tasks: [{ id: 'old' }] };
  assert.deepEqual(rebaseContextDraft(latest, clone(EMPTY_CONTEXT)), EMPTY_CONTEXT);
});
test('minutes cannot be zero, fractional or exceed one day', () => {
  for (const value of [0, -1, 1.5, 1441, NaN]) assert.throws(() => validateContext({ ...clone(EMPTY_CONTEXT), available_minutes: value }));
  assert.equal(validateContext({ ...clone(EMPTY_CONTEXT), available_minutes: 60 }).available_minutes, 60);
});
test('dependencies reject cycles, missing tasks and blank names', () => {
  const a = { id: 'a', title: '자료', depends_on: ['b'] }, b = { id: 'b', title: '초안', depends_on: ['a'] };
  assert.throws(() => validateContext({ ...clone(EMPTY_CONTEXT), tasks: [a, b] }), /서로/);
  assert.throws(() => validateContext({ ...clone(EMPTY_CONTEXT), tasks: [a] }), /삭제된/);
  assert.throws(() => validateContext({ ...clone(EMPTY_CONTEXT), tasks: [{ ...a, title: ' ', depends_on: [] }] }), /이름/);
  assert.doesNotThrow(() => validateContext({ ...clone(EMPTY_CONTEXT), tasks: [a, { ...b, depends_on: [] }] }));
});
test('form values become strict API integers and optional estimates stay null', () => {
  assert.deepEqual(recordPayload({ date: '2026-10-20', task_name: ' 가상 검증 ', category: '취업', value: '12', estimated_minutes: '', memo: ' <b>문자 그대로</b> ' }), { date: '2026-10-20', task_name: '가상 검증', category: '취업', value: 12, estimated_minutes: null, memo: '<b>문자 그대로</b>' });
});
test('missing measurements stay unknown while zero is printed honestly', () => {
  assert.equal(minutes(null), '—'); assert.equal(minutes(0), '0분'); assert.equal(number(6524), '6,524'); assert.match(todayKST(), /^\d{4}-\d{2}-\d{2}$/);
});
test('DELETE accepts an empty 204 and does not try to parse JSON', async () => {
  const calls = [];
  const api = createApi('http://127.0.0.1:8000/', async (url, options) => { calls.push({ url, options }); return new Response(null, { status: 204 }); });
  assert.equal(await api('/api/data/test', { method: 'DELETE' }), null);
  assert.equal(calls[0].url, 'http://127.0.0.1:8000/api/data/test'); assert.equal(calls[0].options.method, 'DELETE'); assert.equal(calls[0].options.credentials, 'omit');
});
test('backend validation and conflict errors preserve status and field paths', async () => {
  const api = createApi('http://localhost:8000', async () => Response.json({ error: { code: 'invalid_request', message: '입력 확인', fields: ['value'] } }, { status: 422 }));
  await assert.rejects(api('/api/data', { method: 'POST', body: { value: 0 } }), e => e instanceof ApiError && e.status === 422 && e.fields[0] === 'value');
});
test('paid chat and mutations are sent once on failure, never automatically retried', async () => {
  let calls = 0;
  const api = createApi('http://localhost:8000', async () => { calls++; return Response.json({ error: { code: 'storage_unavailable', message: '저장 확인 필요' } }, { status: 503 }); });
  await assert.rejects(api('/api/chat', { method: 'POST', body: { message: '검증' } }), /저장 확인/);
  assert.equal(calls, 1);
});
test('ambiguous network failures instruct the user to recheck saving', async () => {
  const api = createApi('http://localhost:8000', async () => { throw new DOMException('abort', 'AbortError'); });
  await assert.rejects(api('/api/chat'), e => e.code === 'timeout' && e.message.includes('저장됐을 수도'));
});
test('non-JSON errors are handled without exposing raw upstream HTML', async () => {
  const api = createApi('http://localhost:8000', async () => new Response('<html>private diagnostic</html>', { status: 502 }));
  await assert.rejects(api('/api/data'), e => e.code === 'invalid_response' && !e.message.includes('private diagnostic'));
});
test('configuration cannot embed credentials or unsafe schemes', () => {
  for (const value of ['javascript:alert(1)', 'https://user:secret@example.com', 'https://example.com?key=secret']) assert.throws(() => createApi(value));
});
