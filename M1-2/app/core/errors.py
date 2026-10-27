"""One safe error shape for validation, route, and service failures."""

from __future__ import annotations

import logging
import re

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger("kim_manager")


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, fields: list[str] | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields or []
        super().__init__(code)


def error_response(status_code: int, code: str, message: str, fields: list[str] | None = None,
                   headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "fields": fields or []}},
        headers=headers,
    )


def safe_field_path(location: tuple) -> str:
    parts = []
    for segment in location:
        if segment in {"body", "query", "path", "header"}:
            continue
        if isinstance(segment, int):
            parts.append(str(segment))
        elif isinstance(segment, str) and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,59}", segment):
            parts.append(segment)
        else:
            parts.append("unknown_field")
    return ".".join(parts) or "body"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def application_error(_request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.fields)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = list(dict.fromkeys(safe_field_path(item["loc"]) for item in exc.errors()))[:10]
        return error_response(422, "invalid_request", "입력값의 필수 항목·형식·범위를 확인해 주세요.", fields)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        messages = {
            404: ("not_found", "요청한 주소나 데이터를 찾을 수 없습니다."),
            405: ("method_not_allowed", "이 주소에서 지원하지 않는 요청 방식입니다."),
        }
        code, message = messages.get(exc.status_code, ("request_failed", "요청을 처리할 수 없습니다."))
        return error_response(exc.status_code, code, message, headers=exc.headers)

    # Catch unexpected route/service failures before the server logs raw exception text.
    @app.middleware("http")
    async def protect_errors(request: Request, call_next):
        try:
            return await call_next(request)
        except ResponseValidationError:
            logger.error("Invalid application response")
            return error_response(500, "internal_error", "서버 응답을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.")
        except Exception as exc:
            logger.error("Unhandled application exception (%s)", type(exc).__name__)
            return error_response(500, "internal_error", "요청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
