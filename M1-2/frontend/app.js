import { EMPTY_CONTEXT, MODES, number, minutes, dateTime, todayKST, contextPatch, rebaseContextDraft, validateContext, recordPayload, createApi, createDraftJournal, hasUnsentDraft } from './lib.js?v=20261028d';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const clone = value => structuredClone(value);
const state = { view: 'chat', summary: null, summaryError: null, conversation: null, baseline: clone(EMPTY_CONTEXT), taskDrafts: [], chatBusy: false, loadingConversation: false, recordBusy: false, editingRecord: null, records: null, recordPage: 1, history: null, historyPage: 1, recent: [], summaryRequest: 0, recordRequest: 0, historyRequest: 0 };
let tabStorage, browserStorage;
try { tabStorage = window.sessionStorage; } catch { /* Browsers may deny storage. */ }
try { browserStorage = window.localStorage; } catch { /* The tab copy still helps. */ }
const journal = createDraftJournal(tabStorage, window.KIM_CONFIG?.API_BASE_URL || 'http://127.0.0.1:8000', browserStorage);
let draftKey = journal.active;
let draftReady = false;
let pendingSend = false;
let sendingQuestion = '';
let api;
try { api = createApi(window.KIM_CONFIG?.API_BASE_URL || 'http://127.0.0.1:8000'); }
catch (error) { api = async () => { throw error; }; }
$('#docs-link').href = `${(window.KIM_CONFIG?.API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')}/docs`;

// All remote text goes through textContent; HTML from records or GPT never executes.
function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined) continue;
    if (key === 'text') node.textContent = value;
    else if (key === 'class') node.className = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key in node && !key.startsWith('aria') && !key.startsWith('data')) node[key] = value;
    else node.setAttribute(key, String(value));
  }
  for (const child of [children].flat()) if (child !== null && child !== undefined) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return node;
}
const p = (text, className = '') => el('p', { text, class: className });
const button = (text, handler, className = 'secondary', extra = {}) => el('button', { type: 'button', text, class: className, onclick: handler, ...extra });
function feedback(node, message, isError = false) { node.replaceChildren(p(message)); node.hidden = false; node.dataset.error = String(isError); }
function clearFeedback(node) { node.hidden = true; node.replaceChildren(); }
let toastTimer;
function toast(message) { $('#toast').textContent = message; $('#toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 6500); }
function errorBlock(error, retry, label = '다시 불러오기') {
  return el('div', { class: 'error-state', role: 'alert' }, [p(error.message), button(label, retry), p('처음 연결할 때는 서버 준비에 시간이 걸릴 수 있어요. 자동으로 요청을 반복하지 않아요.', 'small muted')]);
}
function setChatLocked(busy) {
  state.chatBusy = busy;
  $$('.chat-lock, #send-chat, #chat-input, [data-starter], [data-load-conversation], [data-delete-conversation]').forEach(n => { n.disabled = busy; });
  $('#context-fields').disabled = busy;
  $('#chat-form').setAttribute('aria-busy', String(busy));
}
function route(focus = true) {
  const view = location.hash.slice(1);
  if (view === 'main') { $('#main').focus(); return; }
  state.view = ['chat', 'records', 'summary', 'history'].includes(view) ? view : 'chat';
  $$('.view').forEach(n => { n.hidden = n.id !== `view-${state.view}`; });
  $$('[data-nav]').forEach(n => { if (n.dataset.nav === state.view) n.setAttribute('aria-current', 'page'); else n.removeAttribute('aria-current'); });
  const titles = { chat: '김실장 상담', records: '작업 기록', summary: '기록 요약', history: '이전 상담' };
  document.title = `${titles[state.view]} · 김실장`;
  syncChatLayout();
  if (focus) { $(`#${state.view === 'chat' ? 'chat' : state.view}-heading`).focus({ preventScroll: true }); window.scrollTo({ top: 0 }); }
  if (state.view === 'chat' && state.focusComposer) { state.focusComposer = false; $('#chat-input').focus(); }
  if (state.view === 'records' && !state.records) void loadRecords();
  if (state.view === 'summary') { renderSummary(); if (!state.summary) void loadSummary(); }
  if (state.view === 'history') { renderLocalDrafts(); void loadHistory(); }
}
window.addEventListener('hashchange', () => route());
function syncChatLayout() {
  const active = Boolean(state.conversation?.messages?.length || sendingQuestion);
  $('#view-chat').classList.toggle('chat-active', active);
  $('#main').classList.toggle('conversation-mode', state.view === 'chat' && active);
  $('#toggle-reference').hidden = !active;
  $('#send-label').textContent = active ? '보내기' : '김실장에게 물어보기';
  $('#chat-input').rows = active ? 2 : 3;
  $('#chat-input').placeholder = active ? '이어서 이야기해 주세요…' : '김실장님, 지금 이런 고민이 있어요…';
}
$('#toggle-reference').addEventListener('click', () => {
  const open = $('#toggle-reference').getAttribute('aria-expanded') !== 'true';
  $('#toggle-reference').setAttribute('aria-expanded', String(open));
  $('#view-chat').classList.toggle('reference-open', open);
});
function captureDraft() {
  return { question: $('#chat-input').value, mode: $('#chat-mode').value, baseline: clone(state.baseline), seenMessages: state.conversation?.messages?.length || 0,
    context: { goal: $('#context-goal').value, time: $('#context-time').value, constraints: $('#context-constraints').value, tasks: clone(state.taskDrafts) },
    detailsOpen: $('#context-details').open, scrollTop: $('#messages').scrollTop, pending: pendingSend, updatedAt: new Date().toISOString() };
}
function persistDraft() {
  if (!draftReady) return;
  const saved = journal.write(draftKey, captureDraft());
  $('#draft-state').textContent = saved ? `작성 중인 내용은 ${journal.durable ? '이 브라우저' : '이 탭'}에 임시 보관돼요.` : '이 브라우저에서는 임시 보관을 할 수 없어요. 페이지를 닫기 전 내용을 복사해 주세요.';
}
function applyDraft(draft, { rebase = false } = {}) {
  if (!draft) return;
  $('#chat-input').value = draft.question; $('#chat-mode').value = draft.mode;
  const raw = draft.context;
  // Keep server-only updates, and replay only locally edited conditions.
  if (rebase && draft.baseline) {
    const local = { goal: raw.goal.trim() || null, available_minutes: raw.time === '' ? null : Number(raw.time), constraints: raw.constraints.trim() || null, tasks: raw.tasks };
    setContextForm(rebaseContextDraft(state.baseline, contextPatch(local, draft.baseline)));
  } else { $('#context-goal').value = raw.goal; $('#context-time').value = raw.time; $('#context-constraints').value = raw.constraints; state.taskDrafts = clone(raw.tasks); renderTasks(); updateContextSummary(); }
  $('#context-details').open = Boolean(draft.detailsOpen);
  pendingSend = Boolean(draft.pending);
  if (pendingSend) {
    feedback($('#chat-error'), '이전 요청의 저장 여부를 아직 확인하지 못했어요. ‘이전 상담’에서 확인한 뒤 다시 보내 주세요. 질문은 임시 보관했어요.', true);
    $('#chat-error').append(el('a', { href: '#history', text: '이전 상담 확인하기' }));
  }
}
function renderLocalDrafts() {
  const root = $('#local-drafts'); root.replaceChildren();
  const drafts = journal.entries().filter(({ draft }) => hasUnsentDraft(draft));
  root.hidden = !drafts.length;
  if (!drafts.length) return;
  root.append(el('h2', { text: '작성 중인 질문' }), p('브라우저에 임시 보관한 내용이에요. 서버에 저장된 상담과 구분해요.', 'small muted'));
  drafts.forEach(({ id, draft }) => root.append(button(draft.question.trim().slice(0, 70) || '현재 상황을 작성한 상담', () => openDraft(id), 'draft-open')));
}
async function openDraft(id) {
  if (state.chatBusy) return;
  if (id.startsWith('conversation:')) return loadConversation(id.slice(13));
  persistDraft(); draftKey = id; journal.activate(id); state.conversation = null; pendingSend = false; sendingQuestion = ''; state.restoreFailed = false; setChatLocked(false); fillContext(EMPTY_CONTEXT); clearFeedback($('#chat-error')); applyDraft(journal.read(id));
  $('#chat-subtitle').textContent = '작성 중인 질문을 이어서 적어 주세요.'; $('#save-state').textContent = '답변 완료 후 이전 상담에 저장'; renderMessages(); persistDraft(); location.hash = 'chat'; $('#chat-input').focus();
}
$('#chat-form').addEventListener('input', persistDraft);
$('#chat-form').addEventListener('change', persistDraft);
$('#context-details').addEventListener('toggle', persistDraft);
$('#chat-mode').addEventListener('change', persistDraft);
window.addEventListener('pagehide', persistDraft);
document.addEventListener('visibilitychange', () => {
  if (document.hidden) persistDraft();
  else { void loadRecent(); if (state.view === 'history') void loadHistory(); }
});

async function loadSummary() {
  const request = ++state.summaryRequest;
  $('#refresh-summary').disabled = true; $('#refresh-reference').disabled = true;
  if (!state.summary) { $('#reference-summary').replaceChildren(p('기록을 불러오고 있어요…', 'muted')); $('#summary-content').replaceChildren(p('서버에서 기록을 분석하고 있어요…', 'empty-state')); }
  try {
    const data = await api('/api/data/summary');
    if (request !== state.summaryRequest) return;
    state.summary = data; state.summaryError = null;
  } catch (error) { if (request !== state.summaryRequest) return; state.summaryError = error; }
  finally { if (request === state.summaryRequest) { $('#refresh-summary').disabled = false; $('#refresh-reference').disabled = false; renderReference(); renderSummary(); } }
}
function renderReference() {
  const root = $('#reference-summary'); root.replaceChildren();
  if (state.summaryError) root.append(errorBlock(state.summaryError, loadSummary));
  if (!state.summary) return;
  const { summary: s } = state.summary;
  if (state.summaryError) root.append(p(`아래는 마지막으로 확인한 요약이에요. 기준일 ${s.as_of || '없음'}`, 'small muted'));
  root.append(p(s.period ? `${s.period.start} — ${s.period.end}` : '아직 작업 기록이 없어요.', 'muted'));
  root.append(el('div', { class: 'reference-count num' }, [number(s.count), el('span', { text: '건의 작업 기록' })]));
  if (!s.count) { root.append(p('첫 기록을 남기면 시간과 변화의 근거가 생겨요.', 'reference-note')); return; }
  const dl = el('dl', { class: 'reference-values' });
  [['기록된 총 시간', minutes(s.total_minutes)], ['작업 한 건 평균', minutes(s.average_minutes_per_record)]]
    .forEach(([label, value]) => dl.append(el('div', {}, [el('dt', { text: label }), el('dd', { text: value })])));
  root.append(dl, p(`데이터 기준일 ${s.as_of || '없음'} · 가상 기록`, 'reference-note'));
  const t = s.recent_trend;
  if (t.direction !== 'insufficient_data') root.append(p(`최근 7일 ${minutes(t.recent_total_minutes)} · 이전 7일 대비 ${t.change_percent == null ? '비교 불가' : `${t.change_percent > 0 ? '+' : ''}${number(t.change_percent, 2)}%`}`, 'small muted'));
}
function metric(label, value, unit, note) {
  return el('div', { class: 'metric' }, [p(label, 'metric-label'), el('p', { class: 'metric-value' }, [number(value, 2), unit ? el('span', { text: unit }) : null]), note ? p(note) : null]);
}
function renderSummary() {
  const root = $('#summary-content'); root.replaceChildren();
  if (state.summaryError) root.append(errorBlock(state.summaryError, loadSummary));
  if (!state.summary) { if (!state.summaryError) root.append(p('기록 요약을 불러오고 있어요…', 'empty-state')); return; }
  const { summary: s, data_revision: revision, generated_at: generated } = state.summary;
  root.append(el('div', { class: 'summary-meta' }, [el('span', { text: s.period ? `${s.period.start} — ${s.period.end}` : '기록 기간 없음' }), el('span', { text: `기준일 ${s.as_of || '없음'} · ${number(s.count)}건` }), el('span', { text: `요약 v${revision} · ${dateTime(generated)} 생성` })]));
  if (!s.count) { root.append(el('div', { class: 'panel empty-state' }, [el('h2', { text: '분석할 작업 기록이 아직 없어요.' }), p('첫 가상 기록을 남기면 통계와 상담 근거가 생겨요.'), button('첫 기록 남기기', () => { location.hash = 'records'; })])); return; }
  root.append(el('div', { class: 'metrics' }, [metric('기록된 총 시간', s.total_minutes, '분', `${s.recorded_days}일에 걸친 ${s.count}건`), metric('작업 한 건 평균', s.average_minutes_per_record, '분', `최소 ${minutes(s.min_minutes)} · 최대 ${minutes(s.max_minutes)}`), metric('기록한 날의 하루 평균', s.average_minutes_per_recorded_day, '분', '기록이 있는 날짜만 계산'), metric('기록이 없는 날', s.unrecorded_days, '일', '휴식일·0분으로 해석하지 않아요')]));
  const grid = el('div', { class: 'summary-grid' });
  const t = s.recent_trend;
  const trend = el('section', { class: 'panel' }, [el('h2', { text: '최근 작업 시간의 변화' })]);
  if (t.direction === 'insufficient_data') trend.append(p('비교할 기록이 충분하지 않아요. 두 기간의 기록을 확인해 주세요.', 'empty-state'));
  else {
    const delta = t.change_percent == null ? '변화율을 계산할 수 없어요.' : `이전 7일 대비 ${t.change_percent > 0 ? '+' : ''}${number(t.change_percent, 2)}% · ${{ increase: '증가', decrease: '감소', stable: '유지' }[t.direction]}`;
    const range = (start, end) => el('p', { class: 'trend-period' }, [el('span', { text: start }), el('span', { text: `~ ${end}` })]);
    trend.append(el('div', { class: 'trend-comparison' }, [el('div', {}, [range(t.previous_start, t.previous_end), p(minutes(t.previous_total_minutes), 'num'), p(`${t.previous_record_count}건 · 기록한 날 ${t.previous_recorded_days}일`)]), el('div', {}, [range(t.recent_start, t.recent_end), p(minutes(t.recent_total_minutes), 'num'), p(`${t.recent_record_count}건 · 기록한 날 ${t.recent_recorded_days}일`)])]), p(delta, 'trend-finding'), p(`기준일에서 거슬러 올라간 두 7일 구간 비교 · ±${t.threshold_percent}%를 기준으로 구분해요. 시간의 증감이 효율의 좋고 나쁨을 뜻하지는 않아요.`, 'summary-note'));
  }
  grid.append(trend);
  const cats = el('section', { class: 'panel' }, [el('h2', { text: '어떤 일에 시간을 썼을까요?' })]);
  s.categories.forEach(c => cats.append(el('div', { class: 'category-row' }, [el('span', { text: c.category }), el('div', { class: 'bar-track', 'aria-hidden': 'true' }, [el('div', { class: 'bar', style: `width:${Math.max(0, Math.min(100, c.share_percent))}%` })]), el('div', { class: 'num' }, [minutes(c.total_minutes), el('small', { text: `${number(c.share_percent, 2)}% · ${c.count}건` })])])));
  cats.append(p('전체 기록 시간에서 각 분야가 차지한 비중이에요. 우선순위 점수는 아니에요.', 'summary-note')); grid.append(cats);
  const repeated = el('section', { class: 'panel full' }, [el('div', { class: 'section-inline' }, [el('h2', { text: '반복 작업에서 찾는 자동화의 실마리' }), el('span', { class: 'small muted', text: '횟수·누적 시간 기준 후보' })])]);
  if (!s.repeat_review_candidates.length) repeated.append(p('아직 반복 작업 후보가 없어요. 기록이 쌓이면 다시 살펴볼게요.', 'empty-state'));
  else {
    const table = el('table', { class: 'repeat-table' });
    table.append(el('caption', { class: 'sr-only', text: '반복 작업 후보별 횟수, 누적 시간, 평균 시간과 상담 시작' }));
    table.append(el('thead', {}, [el('tr', {}, [el('th', { scope: 'col', text: '작업' }), el('th', { scope: 'col', text: '횟수', class: 'num' }), el('th', { scope: 'col', text: '누적 시간', class: 'num' }), el('th', { scope: 'col', text: '평균 시간', class: 'num' }), el('th', { scope: 'col', text: '상담', class: 'num' })])]));
    const tbody = el('tbody');
    s.repeat_review_candidates.forEach(c => tbody.append(el('tr', {}, [el('td', { text: c.task_name }, [el('small', { text: c.category })]), el('td', { text: `${c.count}회`, class: 'num', 'data-label': '횟수' }), el('td', { text: minutes(c.total_minutes), class: 'num', 'data-label': '누적' }), el('td', { text: minutes(c.average_minutes), class: 'num', 'data-label': '평균' }), el('td', { class: 'num' }, [button('방법 찾아보기', () => prefill(`가상 기록의 ‘${c.task_name}’ 작업을 줄이는 방법을 함께 설계해 주세요. 자동화할 단계와 사람이 확인할 단계, 작은 검증 순서가 궁금해요.`, 'automation'), 'text-button', { disabled: state.chatBusy })])])));
    table.append(tbody); repeated.append(table);
  }
  repeated.append(p('많이 반복했다는 사실만으로 자동화가 가능하다고 판단하지 않아요. 작업 과정을 확인한 뒤 방법을 제안해요.', 'summary-note')); grid.append(repeated);
  const weeks = el('section', { class: 'panel full' }, [el('h2', { text: '주별로 모아보기' })]);
  const weekList = el('div', { class: 'weekly-list' });
  s.weekly.forEach(w => weekList.append(el('div', { class: 'weekly-row' }, [el('div', { text: `${w.start} — ${w.end}` }, [el('small', { text: `${w.record_count}건 · 기록한 날 ${w.recorded_days}일${w.is_partial ? ' · 부분 주간' : ''}` })]), el('span', { class: 'num', text: minutes(w.total_minutes) })])));
  weeks.append(weekList, p('첫 기록일부터 7일씩 묶었어요. 기록이 없는 날은 소요 시간을 알 수 없는 날로 남겨요.', 'summary-note')); grid.append(weeks);
  root.append(grid, el('details', { class: 'limitations' }, [el('summary', { text: '이 요약을 읽을 때 기억할 점' }), el('ul', {}, s.limitations.map(l => el('li', { text: l }))) ]));
}

function readContextDraft() {
  return { goal: $('#context-goal').value.trim() || null, available_minutes: $('#context-time').value === '' ? null : Number($('#context-time').value), constraints: $('#context-constraints').value.trim() || null, tasks: clone(state.taskDrafts) };
}
function getContextDraft() { return validateContext(readContextDraft()); }
function fillContext(context) {
  state.baseline = clone(context || EMPTY_CONTEXT);
  setContextForm(state.baseline);
}
function setContextForm(context) {
  state.taskDrafts = clone(context.tasks);
  $('#context-goal').value = context.goal || ''; $('#context-time').value = context.available_minutes ?? ''; $('#context-constraints').value = context.constraints || '';
  renderTasks(); updateContextSummary();
}
function updateContextSummary() {
  const parts = [];
  if ($('#context-time').value) parts.push(`${$('#context-time').value}분`);
  if (state.taskDrafts.length) parts.push(`할 일 ${state.taskDrafts.length}개`);
  if ($('#context-goal').value.trim()) parts.push('목표 입력됨');
  $('#context-summary').textContent = parts.join(' · ') || '선택 입력';
  $('#add-task').disabled = state.taskDrafts.length >= 10;
}
function renderTasks() {
  const root = $('#context-tasks'); root.replaceChildren();
  state.taskDrafts.forEach((task, index) => {
    const title = el('input', { value: task.title, maxLength: 100, placeholder: '예: 지원서 작성', oninput: e => { task.title = e.target.value; updateContextSummary(); } });
    const due = el('input', { type: 'date', value: task.due_date || '', oninput: e => { task.due_date = e.target.value || null; } });
    const importance = el('select', { onchange: e => { task.importance = e.target.value; } }, Object.entries({ unknown: '아직 정하지 않음', high: '높음', medium: '보통', low: '낮음' }).map(([value, text]) => el('option', { value, text, selected: task.importance === value })));
    const dependencies = el('div', { class: 'dependencies' }, [el('span', { class: 'small muted', text: '먼저 끝낼 일' })]);
    state.taskDrafts.filter(t => t.id !== task.id).forEach((other, i) => dependencies.append(el('label', {}, [el('input', { type: 'checkbox', checked: task.depends_on.includes(other.id), onchange: e => { task.depends_on = e.target.checked ? [...task.depends_on, other.id] : task.depends_on.filter(id => id !== other.id); } }), `${state.taskDrafts.indexOf(other) + 1}번 할 일`])));
    if (state.taskDrafts.length < 2) dependencies.append(el('span', { class: 'small muted', text: '다른 할 일을 추가하면 선택할 수 있어요.' }));
    root.append(el('div', { class: 'task-editor' }, [el('div', { class: 'task-editor-head' }, [el('label', { text: `할 일 ${index + 1}` }, [title]), button('제거', () => { state.taskDrafts = state.taskDrafts.filter(t => t.id !== task.id).map(t => ({ ...t, depends_on: t.depends_on.filter(id => id !== task.id) })); renderTasks(); updateContextSummary(); persistDraft(); }, 'text-button', { 'aria-label': `할 일 ${index + 1} 제거` })]), el('div', { class: 'task-options' }, [el('label', { text: `할 일 ${index + 1} 마감일 (선택)` }, [due]), el('label', { text: `할 일 ${index + 1} 중요도` }, [importance])]), dependencies]));
  });
}
$('#add-task').addEventListener('click', () => {
  if (state.taskDrafts.length >= 10) return;
  state.taskDrafts.push({ id: `t_${crypto.randomUUID().replaceAll('-', '').slice(0, 12)}`, title: '', due_date: null, importance: 'unknown', depends_on: [] }); renderTasks(); updateContextSummary();
  persistDraft(); $('#context-tasks .task-editor:last-child input').focus();
});
$('#context-fields').addEventListener('input', updateContextSummary);

function renderPlan(message) {
  const plan = message.plan, ctx = message.context || EMPTY_CONTEXT;
  const names = new Map(ctx.tasks.map(t => [t.id, t.title]));
  const work = plan.tasks.reduce((total, task) => total + task.steps.reduce((n, step) => n + step.minutes, 0), 0);
  const root = el('div', { class: 'execution-plan' }, [el('div', { class: 'plan-budget' }, ['이번 실행 계획', el('span', { text: `작업 ${work}분 + 여유 ${plan.buffer_minutes}분 / 가능 ${plan.available_minutes}분` })])]);
  plan.tasks.forEach(task => {
    const steps = el('ol', {}, task.steps.map(step => el('li', { text: step.action }, [el('span', { text: minutes(step.minutes) })])));
    root.append(el('section', { class: 'plan-task' }, [el('h3', {}, [el('span', { class: 'rank', text: `${task.priority}.` }), names.get(task.task_id) || '할 일']), p(task.reason, 'muted'), el('dl', {}, [el('dt', { text: '이번 완료 기준' }), el('dd', { text: task.completion_criteria }), el('dt', { text: '이 순서로 해보세요' }), el('dd', {}, [steps]), el('dt', { text: '지금 할 첫 행동' }), el('dd', { text: task.first_action })]), el('details', {}, [el('summary', { text: '중간 점검과 시간이 부족할 때의 대안' }), p(task.checkpoint), p(task.fallback)])]));
  });
  if (plan.deferred.length) root.append(el('section', { class: 'plan-deferred' }, [el('h3', { text: '다음으로 미룰 일' }), ...plan.deferred.map(t => p(`${names.get(t.task_id) || '할 일'} · ${t.reason}`))]));
  if (plan.assumptions.length) root.append(el('section', { class: 'plan-assumptions' }, [el('h3', { text: '이 계획에서 둔 가정' }), ...plan.assumptions.map(v => p(v))]));
  return root;
}
function renderMessages({ scroll = false } = {}) {
  const root = $('#messages');
  const messages = state.conversation?.messages || [];
  syncChatLayout();
  if (!messages.length && !sendingQuestion) {
    $('#latest-message').hidden = true;
    root.replaceChildren(welcomeTemplate.cloneNode(true));
    $$('[data-starter]', root).forEach(n => n.addEventListener('click', () => prefill(n.dataset.starter, n.dataset.mode)));
  } else {
    root.replaceChildren();
    messages.forEach(m => {
      const article = el('article', { class: `message message-${m.role}`, 'aria-label': m.role === 'user' ? '나의 메시지' : '김실장의 답변' });
      article.append(el('div', { class: 'message-head' }, [el('strong', { text: m.role === 'user' ? '나' : '김실장' }), el('span', { class: 'small muted', text: MODES[m.mode] || '' }), el('time', { dateTime: m.created_at, text: dateTime(m.created_at) })]));
      article.append(m.role === 'assistant' && m.plan ? renderPlan(m) : p(m.content, 'message-content'));
      if (m.role === 'assistant' && m.evidence) article.append(p(`가상 기록 근거 · ${m.evidence.count}건 · 기준일 ${m.evidence.as_of || '없음'} · 요약 v${m.evidence.data_revision}${m.evidence.period ? ` · ${m.evidence.period.start}~${m.evidence.period.end}` : ''}`, 'message-evidence'));
      root.append(article);
    });
    if (sendingQuestion) root.append(el('article', { class: 'message message-user' }, [el('div', { class: 'message-head' }, [el('strong', { text: '나' }), el('span', { class: 'small muted', text: '답변을 기다리는 중' })]), p(sendingQuestion, 'message-content')]));
  }
  if (scroll) {
    const lastAnswer = sendingQuestion ? null : $$('.message-assistant', root).at(-1);
    root.scrollTop = lastAnswer ? lastAnswer.offsetTop - root.offsetTop - 24 : root.scrollHeight;
    $('#latest-message').hidden = true;
  }
}
const welcomeTemplate = $('#welcome').cloneNode(true);
$('#messages').addEventListener('scroll', () => { const n = $('#messages'); $('#latest-message').hidden = n.scrollHeight - n.scrollTop - n.clientHeight < 100 || !state.conversation?.messages?.length; persistDraft(); });
$('#latest-message').addEventListener('click', () => { const n = $('#messages'); n.scrollTop = n.scrollHeight; $('#latest-message').hidden = true; });
function newChat() {
  if (state.chatBusy) return;
  persistDraft(); draftKey = `new:${crypto.randomUUID()}`; pendingSend = false; sendingQuestion = ''; state.restoreFailed = false;
  state.conversation = null; setChatLocked(false); fillContext(EMPTY_CONTEXT); $('#context-details').open = false; $('#chat-mode').value = 'strategy'; $('#chat-input').value = ''; $('#chat-subtitle').textContent = '무엇부터, 어떻게 할지 함께 정해요.'; $('#save-state').textContent = '답변 완료 후 이전 상담에 저장'; clearFeedback($('#chat-error')); renderMessages(); persistDraft(); $('#chat-input').focus();
}
$('#new-chat').addEventListener('click', newChat);
function prefill(message, mode) {
  if (state.chatBusy) return;
  // A candidate starts a new consultation; never silently posts a paid request.
  if (state.conversation || $('#chat-input').value.trim()) newChat();
  $('#chat-input').value = message; $('#chat-mode').value = mode;
  persistDraft();
  if (location.hash === '#chat') $('#chat-input').focus();
  else { state.focusComposer = true; location.hash = 'chat'; }
  toast('질문 초안을 채웠어요. 내용을 확인한 뒤 물어보기 버튼을 눌러 주세요.');
}
async function loadConversation(id, { preserveInput = false, restore = false } = {}) {
  if (state.chatBusy || state.loadingConversation) return;
  persistDraft();
  const savedDraft = journal.read(`conversation:${id}`);
  const localPatch = preserveInput ? contextPatch(readContextDraft(), state.baseline) : null;
  const localMode = $('#chat-mode').value;
  state.loadingConversation = true; setChatLocked(true); $('#chat-progress').hidden = false; $('#chat-progress-text').textContent = '저장된 상담을 불러오고 있어요…';
  try {
    const { conversation } = await api(`/api/conversations/${encodeURIComponent(id)}`);
    draftKey = `conversation:${id}`; journal.activate(draftKey); pendingSend = false; sendingQuestion = ''; state.restoreFailed = false;
    if (savedDraft?.pending && conversation.messages.length > savedDraft.seenMessages && conversation.messages[savedDraft.seenMessages]?.role === 'user' && conversation.messages[savedDraft.seenMessages]?.content === savedDraft.question.trim()) {
      savedDraft.question = ''; savedDraft.pending = false; savedDraft.context = { goal: conversation.context.goal || '', time: String(conversation.context.available_minutes ?? ''), constraints: conversation.context.constraints || '', tasks: conversation.context.tasks }; savedDraft.baseline = conversation.context;
    }
    state.conversation = conversation; fillContext(conversation.context); $('#chat-mode').value = conversation.mode;
    if (preserveInput) { setContextForm(rebaseContextDraft(conversation.context, localPatch)); $('#chat-mode').value = localMode; }
    if (!preserveInput) { $('#chat-input').value = ''; clearFeedback($('#chat-error')); applyDraft(savedDraft, { rebase: true }); }
    if (!restore) { location.hash = 'chat'; route(false); }
    $('#chat-subtitle').textContent = conversation.title; $('#save-state').textContent = '이전 상담에 저장됨'; if (preserveInput) clearFeedback($('#chat-error')); renderMessages({ scroll: true }); persistDraft();
    if (restore && Number.isFinite(savedDraft?.scrollTop)) $('#messages').scrollTop = savedDraft.scrollTop;
    toast(preserveInput ? '최신 대화를 불러왔어요. 작성한 질문과 바꾼 조건은 그대로 남겨뒀어요.' : '이전 상담과 작성 중인 내용을 불러왔어요.');
  } catch (error) {
    if (restore) {
      state.baseline = clone(savedDraft?.baseline || EMPTY_CONTEXT);
      applyDraft(savedDraft); feedback($('#chat-error'), `${error.message} 작성 중인 질문은 보관했어요. 상담을 불러온 뒤 이어서 보내 주세요.`, true);
      $('#chat-error').append(button('상담 다시 불러오기', () => loadConversation(id, { restore: true }), 'text-button'));
      state.restoreFailed = true;
    } else toast(error.message);
  }
  finally { state.loadingConversation = false; setChatLocked(false); $('#chat-progress').hidden = true; if (restore) { draftReady = true; state.restoreFailed = !state.conversation; $('#send-chat').disabled = state.restoreFailed; persistDraft(); } }
}
$('#chat-form').addEventListener('submit', async event => {
  event.preventDefault(); if (state.chatBusy) return;
  if (state.restoreFailed) return;
  const message = $('#chat-input').value.trim(); if (!message) { $('#chat-input').focus(); return; }
  let patch;
  try { patch = contextPatch(getContextDraft(), state.baseline); }
  catch (error) { feedback($('#chat-error'), error.message, true); $('#context-details').open = true; return; }
  const body = { message, mode: $('#chat-mode').value, ...(state.conversation ? { conversation_id: state.conversation.id } : {}), ...(Object.keys(patch).length ? { context: patch } : {}) };
  const previousMessages = state.conversation?.messages || [];
  pendingSend = true; sendingQuestion = message; persistDraft(); renderMessages({ scroll: true }); $('#context-details').open = false;
  $('#chat-announcement').textContent = '';
  clearFeedback($('#chat-error')); setChatLocked(true); $('#chat-progress').hidden = false; $('#chat-progress-text').textContent = '김실장이 기록을 참고해 답변을 정리하고 있어요…'; $('#save-state').textContent = '답변과 대화를 저장하는 중';
  const slowTimer = setTimeout(() => { $('#chat-progress-text').textContent = '조금 더 살펴보고 있어요. 첫 연결은 서버 준비 때문에 늦을 수 있어요. 답변이 올 때까지 기다려 주세요.'; }, 12000);
  try {
    const result = await api('/api/chat', { method: 'POST', body, timeout: 160000 });
    // Success means the backend committed both messages. GET is safe and unbilled.
    state.conversation = { ...(state.conversation || {}), id: result.conversation_id, context: result.context, mode: result.message.mode, title: state.conversation?.title || message.slice(0, 40), messages: [...previousMessages, { role: 'user', content: message, mode: body.mode, created_at: result.message.created_at }, result.message] };
    journal.remove(draftKey); draftKey = `conversation:${result.conversation_id}`; pendingSend = false; sendingQuestion = '';
    fillContext(result.context); $('#chat-mode').value = result.message.mode; $('#chat-input').value = ''; $('#save-state').textContent = '이전 상담에 자동 저장됐어요'; $('#chat-subtitle').textContent = state.conversation.title;
    persistDraft();
    $('#chat-announcement').textContent = '질문과 답변이 이전 상담에 저장됐어요.';
    renderMessages({ scroll: true });
    state.history = null; void loadRecent();
  } catch (error) {
    sendingQuestion = ''; pendingSend = ['timeout', 'network_error', 'storage_unavailable'].includes(error.code); persistDraft(); renderMessages();
    feedback($('#chat-error'), `${error.message} 질문은 그대로 남겨뒀어요.`, true);
    if (error.status === 409 && state.conversation) $('#chat-error').append(button('최신 대화 불러오기', () => loadConversation(state.conversation.id, { preserveInput: true }), 'text-button'));
    if (['timeout', 'network_error', 'storage_unavailable'].includes(error.code)) $('#chat-error').append(el('a', { href: '#history', text: '이전 상담에서 저장 여부 확인' }));
    $('#save-state').textContent = '저장 결과를 확인해 주세요';
  } finally { clearTimeout(slowTimer); setChatLocked(false); $('#chat-progress').hidden = true; }
});
$('#chat-input').addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !event.isComposing) { event.preventDefault(); $('#chat-form').requestSubmit(); } });

function pagination(root, data, handler) {
  root.replaceChildren(); if (!data?.total) return;
  const start = (data.page - 1) * data.page_size + 1, end = Math.min(data.total, data.page * data.page_size);
  root.append(el('span', { text: `${number(data.total)}건 중 ${start}–${end}` }), el('div', {}, [button('이전', () => handler(data.page - 1), 'secondary', { disabled: data.page <= 1 }), button('다음', () => handler(data.page + 1), 'secondary', { disabled: end >= data.total })]));
}
async function loadRecords(page = state.recordPage) {
  const request = ++state.recordRequest;
  $('#refresh-records').disabled = true; $('#record-list').setAttribute('aria-busy', 'true');
  if (!state.records) $('#record-list').replaceChildren(p('작업 기록을 불러오고 있어요…', 'empty-state'));
  try {
    const data = await api(`/api/data?page=${page}&page_size=10`);
    if (request !== state.recordRequest) return;
    if (!data.items.length && page > 1) { void loadRecords(page - 1); return; }
    state.records = data; state.recordPage = data.page; renderRecords();
  } catch (error) { if (request === state.recordRequest) $('#record-list').replaceChildren(errorBlock(error, () => loadRecords(page))); }
  finally { if (request === state.recordRequest) { $('#refresh-records').disabled = false; $('#record-list').setAttribute('aria-busy', 'false'); } }
}
function renderRecords() {
  const root = $('#record-list'); root.replaceChildren(); const data = state.records;
  $('#record-total').textContent = `${number(data.total)}건`;
  if (!data.items.length) root.append(el('div', { class: 'empty-state' }, [el('h3', { text: '첫 작업 기록을 남겨볼까요?' }), p('완료한 작업과 실제 소요 시간을 입력해 주세요.'), button('기록 입력하기', focusRecordForm)]));
  else {
    const table = el('table', { class: 'record-table' }, [el('caption', { class: 'sr-only', text: '날짜순 작업 기록과 수정·삭제' }), el('thead', {}, [el('tr', {}, [el('th', { scope: 'col', text: '날짜' }), el('th', { scope: 'col', text: '작업·메모' }), el('th', { scope: 'col', text: '실제', class: 'num' }), el('th', { scope: 'col', text: '예상', class: 'num' }), el('th', { scope: 'col', text: '관리', class: 'num' })])])]);
    const tbody = el('tbody');
    data.items.forEach(item => tbody.append(el('tr', {}, [el('td', { class: 'record-date' }, [el('time', { dateTime: item.date, text: item.date })]), el('td', { class: 'record-name' }, [el('strong', { text: item.task_name }), el('small', { text: item.category }), item.memo ? el('details', { class: 'record-note' }, [el('summary', { text: '메모 보기', 'aria-label': `${item.task_name} ${item.date} 메모 보기` }), p(item.memo, 'record-memo')]) : null]), el('td', { class: 'num', text: minutes(item.value), 'data-label': '실제' }), el('td', { class: 'num', text: minutes(item.estimated_minutes), 'data-label': '예상' }), el('td', {}, [el('div', { class: 'row-actions' }, [button('수정', () => editRecord(item), 'text-button', { disabled: state.recordBusy, 'aria-label': `${item.task_name} ${item.date} 수정` }), button('삭제', () => deleteRecord(item), 'text-button delete-action', { disabled: state.recordBusy, 'aria-label': `${item.task_name} ${item.date} 삭제` })])])])));
    table.append(tbody); root.append(table);
  }
  pagination($('#record-pagination'), data, loadRecords);
}
function focusRecordForm() { $('.record-editor').scrollIntoView({ behavior: 'smooth', block: 'start' }); $('#record-form [name=date]').focus({ preventScroll: true }); }
function resetRecordForm() {
  state.editingRecord = null; $('#record-form').reset(); $('#record-form [name=date]').value = todayKST(); $('#record-form-heading').textContent = '작업 기록 추가'; $('#save-record').textContent = '기록 저장'; $('#cancel-record-edit').hidden = true;
}
function editRecord(item) {
  if (state.recordBusy) return;
  state.editingRecord = item.id;
  for (const key of ['date', 'task_name', 'category', 'value', 'estimated_minutes', 'memo']) $(`[name=${key}]`, $('#record-form')).value = item[key] ?? '';
  $('#record-form-heading').textContent = '작업 기록 수정'; $('#save-record').textContent = '수정 저장'; $('#cancel-record-edit').hidden = false; clearFeedback($('#record-feedback')); focusRecordForm();
}
$('#cancel-record-edit').addEventListener('click', () => { resetRecordForm(); clearFeedback($('#record-feedback')); });
$('#jump-record-form').addEventListener('click', () => { if (state.recordBusy) return; resetRecordForm(); clearFeedback($('#record-feedback')); focusRecordForm(); });
function setRecordBusy(busy) {
  state.recordBusy = busy; $('#record-fields').disabled = busy; $('#save-record').disabled = busy; $('#cancel-record-edit').disabled = busy; $('#jump-record-form').disabled = busy;
  if (state.records) renderRecords();
}
$('#record-form').addEventListener('submit', async event => {
  event.preventDefault(); if (state.recordBusy) return;
  const id = state.editingRecord;
  const payload = recordPayload(Object.fromEntries(new FormData(event.currentTarget)));
  setRecordBusy(true); feedback($('#record-feedback'), '기록을 저장하고 있어요…');
  try {
    const result = await api(id ? `/api/data/${encodeURIComponent(id)}` : '/api/data', { method: id ? 'PUT' : 'POST', body: payload });
    resetRecordForm(); feedback($('#record-feedback'), result.warning ? `기록은 저장됐어요. ${result.warning.message}` : id ? '수정한 기록을 저장했어요.' : '새 가상 작업 기록을 저장했어요.');
    await Promise.allSettled([loadRecords(1), loadSummary()]);
    toast(result.warning ? '기록은 저장됐어요. 요약을 다시 확인해 주세요.' : '기록을 저장했어요. 목록과 요약에서 결과를 확인해 주세요.');
  } catch (error) { feedback($('#record-feedback'), `${error.message} 입력은 그대로 남겨뒀어요. 저장 여부가 불확실하면 목록을 먼저 새로고침해 주세요.`, true); }
  finally { setRecordBusy(false); }
});
const dialog = $('#confirm-dialog');
let confirmAction = null;
function confirmDelete(title, description, action) {
  $('#confirm-title').textContent = title; $('#confirm-description').textContent = description; clearFeedback($('#confirm-error')); confirmAction = action; $('#confirm-delete').disabled = false; $('#confirm-cancel').disabled = false; dialog.showModal(); $('#confirm-cancel').focus();
}
$('#confirm-delete').addEventListener('click', async event => {
  event.preventDefault(); if (!confirmAction || $('#confirm-delete').disabled) return;
  $('#confirm-delete').disabled = true; $('#confirm-cancel').disabled = true;
  try { await confirmAction(); dialog.close('delete'); confirmAction = null; }
  catch (error) { feedback($('#confirm-error'), `${error.message} 목록을 다시 확인한 뒤 시도해 주세요.`, true); }
  finally { $('#confirm-delete').disabled = false; $('#confirm-cancel').disabled = false; }
});
dialog.addEventListener('cancel', event => { if ($('#confirm-delete').disabled) event.preventDefault(); });
function deleteRecord(item) {
  confirmDelete('이 작업 기록을 삭제할까요?', `${item.date} · ${item.task_name} · ${item.value}분. 이 기록 한 건이 삭제되고 요약이 다시 계산돼요. 되돌릴 수 없어요. 상담 기록은 남아 있어요.`, async () => {
    setRecordBusy(true);
    try { await api(`/api/data/${encodeURIComponent(item.id)}`, { method: 'DELETE' }); if (state.editingRecord === item.id) resetRecordForm(); await Promise.allSettled([loadRecords(), loadSummary()]); toast('작업 기록 한 건을 삭제했어요.'); }
    finally { setRecordBusy(false); }
  });
}

async function loadHistory(page = state.historyPage) {
  const request = ++state.historyRequest;
  $('#refresh-history').disabled = true;
  if (!state.history) $('#history-list').replaceChildren(p('이전 상담을 불러오고 있어요…', 'empty-state'));
  try {
    const data = await api(`/api/conversations?page=${page}&page_size=20`);
    if (request !== state.historyRequest) return;
    if (!data.items.length && page > 1) { void loadHistory(page - 1); return; }
    state.history = data; state.historyPage = data.page; renderHistory();
  } catch (error) { if (request === state.historyRequest) $('#history-list').replaceChildren(errorBlock(error, () => loadHistory(page))); }
  finally { if (request === state.historyRequest) $('#refresh-history').disabled = state.chatBusy; }
}
function renderHistory() {
  const data = state.history, root = $('#history-list'); root.replaceChildren(); $('#history-total').textContent = `${number(data.total)}건`;
  if (!data.items.length) root.append(el('div', { class: 'empty-state' }, [el('h3', { text: '아직 저장된 상담이 없어요.' }), p('김실장에게 질문하면 답변과 함께 자동으로 저장돼요.'), button('첫 상담 시작하기', () => { newChat(); location.hash = 'chat'; }, 'secondary', { disabled: state.chatBusy })]));
  data.items.forEach(item => root.append(el('article', { class: 'history-row' }, [el('button', { type: 'button', class: 'history-open', disabled: state.chatBusy, 'data-load-conversation': item.id, onclick: () => loadConversation(item.id) }, [el('strong', { text: item.title }), p(item.last_message_preview || '아직 메시지가 없는 상담이에요.'), el('small', {}, [el('time', { dateTime: item.updated_at, text: dateTime(item.updated_at) }), ` · 메시지 ${item.message_count}개 · 이어서 보기`])]), button('삭제', () => deleteConversation(item), 'text-button delete-action', { 'data-delete-conversation': item.id, 'aria-label': `${item.title} 상담 삭제`, disabled: state.chatBusy })])));
  pagination($('#history-pagination'), data, loadHistory);
}
async function loadRecent() {
  try {
    const data = await api('/api/conversations?page=1&page_size=3'); state.recent = data.items;
    const root = $('#recent-conversations'); root.replaceChildren();
    if (!data.items.length) root.append(p('첫 상담이 이곳에 쌓여요.', 'small muted'));
    data.items.forEach(item => root.append(el('div', { class: 'recent-item' }, [button(item.title, () => loadConversation(item.id), '', { 'data-load-conversation': item.id, disabled: state.chatBusy }), el('time', { dateTime: item.updated_at, text: dateTime(item.updated_at) })])));
  } catch (error) { $('#recent-conversations').replaceChildren(errorBlock(error, loadRecent)); }
}
function deleteConversation(item) {
  if (state.chatBusy) return;
  confirmDelete('이 상담을 삭제할까요?', `‘${item.title}’의 메시지 ${item.message_count}개와 상담 조건을 모두 삭제해요. 되돌릴 수 없어요. 작업 기록은 그대로 남아요.`, async () => {
    await api(`/api/conversations/${encodeURIComponent(item.id)}`, { method: 'DELETE' });
    if (state.conversation?.id === item.id) { draftReady = false; newChat(); draftReady = true; persistDraft(); }
    journal.remove(`conversation:${item.id}`);
    await Promise.allSettled([loadHistory(), loadRecent()]); toast('선택한 상담을 삭제했어요. 작업 기록은 그대로예요.');
  });
}
$('#refresh-reference').addEventListener('click', loadSummary);
$('#refresh-summary').addEventListener('click', loadSummary);
$('#refresh-records').addEventListener('click', () => loadRecords());
$('#refresh-history').addEventListener('click', () => loadHistory());
$('#record-form [name=date]').max = todayKST();
resetRecordForm(); fillContext(EMPTY_CONTEXT); renderMessages(); route(false);
const startupDraft = journal.read();
if (draftKey.startsWith('conversation:')) {
  // Restore with GET only. Never replay a model request after reload or tab return.
  void loadConversation(draftKey.slice(13), { restore: true });
} else { applyDraft(startupDraft); draftReady = true; persistDraft(); }
if (state.view !== 'summary') void loadSummary();
void loadRecent();
