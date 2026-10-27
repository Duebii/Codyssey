from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.routers.dependencies import get_manager
from app.schemas.common import DocumentId, ErrorResponse, RecordPagination
from app.schemas.records import RecordInput, RecordListResponse, RecordResponse
from app.schemas.summaries import SummaryResponse
from app.services.manager import ManagerService

router = APIRouter(prefix="/api/data", tags=["작업 기록"], responses={
    404: {"model": ErrorResponse, "description": "해당 출처의 기록이 없음"},
    409: {"model": ErrorResponse, "description": "기록 ID 충돌"},
    422: {"model": ErrorResponse, "description": "입력 검증 실패"},
    503: {"model": ErrorResponse, "description": "Firebase 설정·저장소 연결 또는 요약 준비 필요"},
})
Manager = Annotated[ManagerService, Depends(get_manager)]


@router.post("", status_code=201, response_model=RecordResponse, summary="가상 작업 기록 추가")
def create_record(payload: RecordInput, manager: Manager):
    return manager.records.create(payload)


@router.get("", response_model=RecordListResponse, summary="가상 작업 기록 목록 조회")
def list_records(pagination: Annotated[RecordPagination, Query()], manager: Manager):
    return manager.records.list(pagination.page, pagination.page_size)


@router.get("/summary", response_model=SummaryResponse, summary="최신 작업 기록 분석·요약 조회")
def get_summary(manager: Manager):
    return manager.summary()


@router.put("/{id}", response_model=RecordResponse, summary="가상 작업 기록 전체 수정")
def update_record(id: DocumentId, payload: RecordInput, manager: Manager):
    return manager.records.update(id, payload)


@router.delete("/{id}", status_code=204, summary="가상 작업 기록 삭제")
def delete_record(id: DocumentId, manager: Manager):
    manager.records.delete(id)
    return Response(status_code=204)
