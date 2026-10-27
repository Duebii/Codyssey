from fastapi import APIRouter

from app.schemas.common import HealthResponse
from app.services.manager import health

router = APIRouter(tags=["서버 상태"])


@router.get("/api/health", response_model=HealthResponse, summary="외부 키 없이 서버 실행 상태 확인")
def get_health():
    return health()
