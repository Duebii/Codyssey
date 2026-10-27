from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, load_settings
from app.core.errors import install_error_handlers
from app.routers import chat, conversations, health, records
from app.schemas.common import ErrorResponse
from app.repositories.records import RecordRepository
from app.repositories.conversations import ConversationRepository
from app.services.manager import ManagerService
from app.core.openai_client import AIGateway


def create_app(settings: Settings | None = None, record_repository: RecordRepository | None = None,
               conversation_repository: ConversationRepository | None = None, ai_gateway: AIGateway | None = None) -> CORSMiddleware:
    settings = settings if settings is not None else load_settings()
    api = FastAPI(
        title="김실장 · AI 업무 전략 비서",
        version="0.7.0",
        description=("7단계: 가상 기록 CRUD·최신 요약을 근거로 김실장이 우선순위·실행 전략·자동화 설계를 상담합니다. "
                     "GPT 응답 검증 후 질문·답변을 함께 저장합니다. 외부 인증은 요청할 때 읽으며 오류를 성공으로 표시하지 않습니다."),
        debug=False,
        responses={500: {"model": ErrorResponse, "description": "안전하게 처리한 서버 오류"}},
    )
    api.state.settings = settings
    api.state.manager = ManagerService(record_repository=record_repository, conversation_repository=conversation_repository, ai_gateway=ai_gateway)
    install_error_handlers(api)
    for router in (health.router, records.router, conversations.router, chat.router):
        api.include_router(router)
    # Wrap the entire app so validation and unexpected-error responses also have CORS headers.
    return CORSMiddleware(
        app=api,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
        max_age=600,
    )
