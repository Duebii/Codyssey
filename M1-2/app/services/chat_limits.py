"""Small single-process demo guard; rolling windows count attempts, not successes."""
from collections import deque
from contextlib import contextmanager
from threading import Lock
from time import monotonic

from app.core.errors import ApiError


class ChatGuard:
    def __init__(self, *, clock=monotonic, client_per_minute=6, total_per_minute=10,
                 daily_model_calls=100, concurrent=2):
        self.clock = clock
        self.client_limit, self.total_limit = client_per_minute, total_per_minute
        self.daily_limit, self.concurrent_limit = daily_model_calls, concurrent
        self.requests = deque()
        self.calls = deque()
        self.active = 0
        self.busy = set()
        self.lock = Lock()

    @contextmanager
    def request(self, client: str, conversation_id: str | None):
        with self.lock:
            now = self.clock()
            while self.requests and self.requests[0][0] <= now - 60:
                self.requests.popleft()
            if len(self.requests) >= self.total_limit or sum(owner == client for _, owner in self.requests) >= self.client_limit:
                raise ApiError(429, "rate_limited", "상담은 분당 사용자 6회·서버 전체 10회까지 가능합니다. 잠시 후 다시 시도해 주세요.")
            if self.active >= self.concurrent_limit:
                raise ApiError(429, "rate_limited", "진행 중인 상담이 많습니다. 응답이 끝난 뒤 다시 시도해 주세요.")
            if conversation_id is not None and conversation_id in self.busy:
                raise ApiError(409, "conversation_conflict", "이 상담의 이전 답변이 생성 중입니다. 완료 후 이어서 질문해 주세요.")
            self.requests.append((now, client))
            self.active += 1
            if conversation_id is not None:
                self.busy.add(conversation_id)
        try:
            yield
        finally:
            with self.lock:
                self.active -= 1
                self.busy.discard(conversation_id)

    def charge_model_call(self):
        with self.lock:
            now = self.clock()
            while self.calls and self.calls[0] <= now - 86400:
                self.calls.popleft()
            if len(self.calls) >= self.daily_limit:
                raise ApiError(429, "rate_limited", "시연 서버의 최근 24시간 GPT 호출 한도에 도달했습니다. 자동 재호출하지 않습니다.")
            self.calls.append(now)
