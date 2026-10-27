from fastapi import Request

from app.services.manager import ManagerService


def get_manager(request: Request) -> ManagerService:
    return request.app.state.manager
