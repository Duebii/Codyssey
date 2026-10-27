"""Lazy Firebase client creation. No SDK initialization during server startup."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Mapping
from uuid import uuid4

from dotenv import dotenv_values

from app.core.config import PROJECT_ROOT
from app.repositories.records import RepositoryUnavailable

MISSING_CREDENTIALS = (
    "Firebase 인증 정보가 비어 있습니다. 프로젝트·Firestore·서비스 계정 키를 준비해 주세요. "
    "요청한 내용은 저장·수정·삭제되지 않았습니다."
)


def read_service_account(env_file: Path | None = None, environ: Mapping[str, str] | None = None) -> dict:
    path = PROJECT_ROOT / ".env" if env_file is None else env_file
    try:
        values = dict(dotenv_values(path, interpolate=False, encoding="utf-8-sig")) if path.is_file() else {}
        values.update(os.environ if environ is None else environ)
        raw = (values.get("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip()
        location = (values.get("FIREBASE_SERVICE_ACCOUNT_PATH") or "").strip()
        if not raw and not location:
            raise RepositoryUnavailable(MISSING_CREDENTIALS)
        if raw and location:
            raise RepositoryUnavailable("Firebase 인증 정보는 JSON 또는 PATH 중 하나만 설정하세요.")
        if location:
            key_path = Path(location).expanduser()
            if not key_path.is_absolute():
                key_path = PROJECT_ROOT / key_path
            if not key_path.is_file() or key_path.stat().st_size > 1_000_000:
                raise RepositoryUnavailable("서비스 계정 파일의 존재·크기·읽기 권한을 확인해 주세요.")
            raw = key_path.read_text(encoding="utf-8-sig")
        if len(raw.encode("utf-8")) > 1_000_000:
            raise RepositoryUnavailable("서비스 계정 JSON의 크기를 확인해 주세요.")
        info = json.loads(raw)
        required = ("project_id", "client_email", "private_key", "token_uri")
        if not isinstance(info, dict) or info.get("type") != "service_account" or any(
            not isinstance(info.get(field), str) or not info[field].strip() for field in required
        ):
            raise RepositoryUnavailable("Firebase 웹 설정이 아닌 서비스 계정 JSON의 필수 필드를 확인해 주세요.")
        if info["token_uri"] not in {"https://oauth2.googleapis.com/token", "https://accounts.google.com/o/oauth2/token"}:
            raise RepositoryUnavailable("서비스 계정의 공식 Google 인증 주소를 확인해 주세요.")
        return info
    except RepositoryUnavailable:
        raise
    except Exception:
        # Never include file paths, raw JSON, key text, or SDK error strings.
        raise RepositoryUnavailable("서비스 계정 설정을 읽을 수 없습니다. 파일·JSON 형식·권한을 확인해 주세요.") from None


class FirebaseClientProvider:
    def __init__(self, env_file: Path | None = None, environ: Mapping[str, str] | None = None):
        self.env_file = env_file
        self.environ = environ
        self._client = None
        self._lock = Lock()

    def get(self):
        with self._lock:
            if self._client is not None:
                return self._client
            info = read_service_account(self.env_file, self.environ)
            firebase_app = None
            try:
                import firebase_admin
                from firebase_admin import credentials, firestore

                certificate = credentials.Certificate(info)
                firebase_app = firebase_admin.initialize_app(
                    certificate, {"projectId": info["project_id"]}, name=f"kim-manager-{uuid4().hex}",
                )
                self._client = firestore.client(app=firebase_app)
            except Exception:
                if firebase_app is not None:
                    try:
                        firebase_admin.delete_app(firebase_app)
                    except Exception:
                        pass
                raise RepositoryUnavailable("Firebase 초기화에 실패했습니다. 서비스 계정·프로젝트·SDK 설정을 확인해 주세요.") from None
            return self._client
