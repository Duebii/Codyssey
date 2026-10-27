from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.routers.dependencies import get_manager
from app.schemas.common import ConversationPagination, DocumentId, ErrorResponse
from app.schemas.conversations import ConversationInput, ConversationListResponse, ConversationResponse
from app.services.manager import ManagerService

router = APIRouter(prefix="/api/conversations", tags=["대화 기록"], responses={
    404: {"model": ErrorResponse, "description": "해당 출처의 대화가 없음"},
    409: {"model": ErrorResponse, "description": "대화 버전 충돌·저장 한도"},
    413: {"model": ErrorResponse, "description": "대화 저장 크기 초과"},
    422: {"model": ErrorResponse, "description": "입력 검증 실패"},
    503: {"model": ErrorResponse, "description": "Firestore 설정·연결·저장된 대화 구조 확인 필요"},
})
Manager = Annotated[ManagerService, Depends(get_manager)]


@router.post("", status_code=201, response_model=ConversationResponse, summary="새 상담 저장")
def create_conversation(payload: ConversationInput, manager: Manager):
    return manager.conversations.create(payload)


@router.get("", response_model=ConversationListResponse, summary="상담 목록·미리보기 조회")
def list_conversations(pagination: Annotated[ConversationPagination, Query()], manager: Manager):
    return manager.conversations.list(pagination.page, pagination.page_size)


@router.get("/{id}", response_model=ConversationResponse, summary="상담 조건과 전체 메시지 불러오기")
def get_conversation(id: DocumentId, manager: Manager):
    return manager.conversations.get(id)


@router.delete("/{id}", status_code=204, summary="선택한 상담 삭제")
def delete_conversation(id: DocumentId, manager: Manager):
    manager.conversations.delete(id)
    return Response(status_code=204)
