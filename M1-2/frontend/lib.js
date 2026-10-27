// Small pure helpers shared by the UI and its contract tests.
export const EMPTY_CONTEXT = { goal: null, available_minutes: null, tasks: [], constraints: null };
export const MODES = { strategy: "우선순위·실행 전략", automation: "자동화 설계", review: "기록 돌아보기" };
export const number = (v, digits = 0) => v == null ? "—" : new Intl.NumberFormat("ko-KR", { maximumFractionDigits: digits }).format(v);
export const minutes = (v) => v == null ? "—" : `${number(v, 2)}분`;
export function dateTime(v) {
  const d = new Date(v);
  return Number.isNaN(d.valueOf()) ? "—" : new Intl.DateTimeFormat("ko-KR", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Seoul" }).format(d);
}
export function todayKST() { return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(new Date()); }
export function contextPatch(current, baseline) {
  return Object.fromEntries(Object.keys(EMPTY_CONTEXT).filter(k => JSON.stringify(current[k]) !== JSON.stringify(baseline[k])).map(k => [k, current[k]]));
}
export function rebaseContextDraft(latest, localPatch) {
  // Latest server values remain the baseline; only actual local edits win.
  return structuredClone({ ...latest, ...localPatch });
}
export function validateContext(ctx) {
  if (ctx.available_minutes !== null && (!Number.isInteger(ctx.available_minutes) || ctx.available_minutes < 1 || ctx.available_minutes > 1440)) throw new Error("가능 시간은 1~1,440분 사이의 정수로 입력해 주세요.");
  if (ctx.tasks.length > 10) throw new Error("할 일은 최대 10개까지 입력할 수 있어요.");
  const tasks = new Map(ctx.tasks.map(t => [t.id, t]));
  const visiting = new Set(), visited = new Set();
  function visit(id) {
    if (visiting.has(id)) throw new Error("선행 작업이 서로를 가리키고 있어요. 순서를 확인해 주세요.");
    if (visited.has(id)) return;
    const t = tasks.get(id);
    if (!t) throw new Error("삭제된 선행 작업을 다시 선택해 주세요.");
    if (!t.title.trim()) throw new Error("할 일의 이름을 입력해 주세요.");
    visiting.add(id);
    t.depends_on.forEach(visit);
    visiting.delete(id); visited.add(id);
  }
  ctx.tasks.forEach(t => visit(t.id));
  return ctx;
}
export function recordPayload(form) {
  return { date: form.date.trim(), task_name: form.task_name.trim(), category: form.category,
    value: Number(form.value), estimated_minutes: form.estimated_minutes === "" ? null : Number(form.estimated_minutes), memo: form.memo.trim() };
}
export class ApiError extends Error {
  constructor(message, code, status = 0, fields = []) { super(message); Object.assign(this, { code, status, fields }); }
}
export function createApi(baseURL, transport = fetch) {
  const base = new URL(baseURL);
  if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password || base.search || base.hash) throw new Error("API 서버 주소 설정을 확인해 주세요.");
  return async function api(path, { method = "GET", body, timeout = 45000 } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await transport(`${base.href.replace(/\/$/, '')}${path}`, {
        method, signal: controller.signal, cache: "no-store", credentials: "omit",
        ...(body !== undefined ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {})
      });
      if (response.status === 204) return null;
      let data;
      try { data = await response.json(); } catch { throw new ApiError("서버 응답을 읽지 못했어요. 잠시 후 목록을 새로 확인해 주세요.", "invalid_response", response.status); }
      if (!response.ok) {
        const error = data?.error;
        throw new ApiError(error?.message || "요청을 처리하지 못했어요. 입력을 확인한 뒤 다시 시도해 주세요.", error?.code || "request_failed", response.status, error?.fields || []);
      }
      return data;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(error.name === 'AbortError' ? "응답을 기다리는 시간이 길어졌어요. 저장됐을 수도 있으니 목록·이전 상담을 확인한 뒤 다시 시도해 주세요." : "서버에 연결하지 못했어요. 서버 준비 중일 수 있으니 잠시 후 다시 확인해 주세요.", error.name === 'AbortError' ? "timeout" : "network_error");
    } finally { clearTimeout(timer); }
  };
}
