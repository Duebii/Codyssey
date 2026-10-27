from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.routers.dependencies import get_manager
from app.schemas.chat import ChatInput, ChatResponse
from app.schemas.common import ErrorResponse
from app.services.manager import ManagerService

router = APIRouter(prefix="/api/chat", tags=["김실장 상담"], responses={
    404: {"model": ErrorResponse, "description": "없는 상담"},
    409: {"model": ErrorResponse, "description": "대화 한도 또는 동시 변경"},
    413: {"model": ErrorResponse, "description": "상담 입력·저장 크기 한도"},
    422: {"model": ErrorResponse, "description": "질문·시간·할 일 조건 검증 실패"},
    429: {"model": ErrorResponse, "description": "요청 횟수·모델 호출 한도"},
    502: {"model": ErrorResponse, "description": "GPT 연결·응답 검증 실패"},
    503: {"model": ErrorResponse, "description": "키·요약·저장소 사용 불가"},
    504: {"model": ErrorResponse, "description": "GPT 요청 시간 초과"},
})


@router.post("", response_model=ChatResponse, summary="최신 가상 기록으로 상담하고 질문·답변 자동 저장")
def chat(payload: ChatInput, request: Request, manager: Annotated[ManagerService, Depends(get_manager)]):
    # Do not trust arbitrary client-supplied Forwarded/X-Forwarded-For headers.
    return manager.chat(payload, request.client.host if request.client else "unknown")
