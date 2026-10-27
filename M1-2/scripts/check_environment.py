"""Offline setup checks. Never prints credentials or calls external services."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGES = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "firebase-admin": "firebase_admin",
    "openai": "openai",
    "python-dotenv": "dotenv",
    "pydantic": "pydantic",
    "tzdata": "tzdata",
    "pytest": "pytest",
    "httpx": "httpx",
}


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    message: str


def read_environment(path: Path, process: Mapping[str, str] | None = None) -> dict[str, str]:
    """Read one explicit .env file; OS values win, including explicit blanks."""
    from dotenv import dotenv_values

    file_values = dotenv_values(path, interpolate=False, encoding="utf-8-sig") if path.is_file() else {}
    values = {key: value for key, value in file_values.items() if value is not None}
    values.update(os.environ if process is None else process)
    return values


def is_valid_address(value: str, *, origin: bool, production: bool) -> bool:
    if not value or any(character.isspace() for character in value) or "*" in value:
        return False
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return False
    if parts.username is not None or parts.password is not None or parts.query or parts.fragment:
        return False
    if port is not None and not 1 <= port <= 65535:
        return False
    if parts.path not in ({""} if origin else {"", "/"}):
        return False
    if parts.scheme == "http" and (production or parts.hostname not in {"localhost", "127.0.0.1", "::1"}):
        return False
    return True


def check_public_settings(values: Mapping[str, str]) -> list[Check]:
    checks = []
    environment = values.get("APP_ENV", "development").strip()
    valid_environment = environment in {"development", "production"}
    checks.append(Check("APP_ENV", "PASS" if valid_environment else "FAIL",
                        "실행 환경 확인" if valid_environment else "development 또는 production을 입력하세요."))
    origins = values.get("ALLOWED_ORIGINS", "").strip()
    if not origins:
        checks.append(Check("ALLOWED_ORIGINS", "MISSING", "프론트엔드 주소를 쉼표로 구분해 입력하세요."))
    else:
        valid = all(is_valid_address(item.strip(), origin=True, production=environment == "production")
                    for item in origins.split(","))
        checks.append(Check("ALLOWED_ORIGINS", "PASS" if valid else "FAIL",
                            "허용 출처 형식 확인" if valid else "경로·후행 /·와일드카드 없이 출처를 입력하세요. HTTP는 로컬 개발만 허용합니다."))
    base_url = values.get("API_BASE_URL", "").strip()
    if not base_url:
        checks.append(Check("API_BASE_URL", "MISSING", "백엔드 주소를 입력하세요."))
    else:
        valid = is_valid_address(base_url, origin=False, production=environment == "production")
        checks.append(Check("API_BASE_URL", "PASS" if valid else "FAIL",
                            "백엔드 주소 형식 확인" if valid else "/api·쿼리·인증 정보가 없는 서버 주소를 입력하세요. 배포 환경은 HTTPS를 사용합니다."))
    return checks


def check_openai_key(values: Mapping[str, str]) -> Check:
    key = values.get("OPENAI_API_KEY", "").strip()
    placeholders = ("your", "replace", "example", "changeme", "sk-...")
    if not key or key.lower().startswith(placeholders):
        return Check("OPENAI_API_KEY", "MISSING", "발급한 키를 로컬 .env에 입력하세요. 키 내용은 출력하지 않습니다.")
    if len(key) < 20 or any(character.isspace() for character in key):
        return Check("OPENAI_API_KEY", "FAIL", "키 형식을 확인하세요. 공백이나 줄바꿈이 포함되면 안 됩니다.")
    return Check("OPENAI_API_KEY", "PASS", "값의 존재·기본 형식만 확인했습니다. 유효성·잔액·권한은 확인하지 않았습니다.")


def check_firebase_credentials(values: Mapping[str, str], root: Path = PROJECT_ROOT) -> Check:
    raw = values.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    location = values.get("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
    name = "FIREBASE_SERVICE_ACCOUNT"
    if raw and location:
        return Check(name, "FAIL", "JSON 또는 PATH 중 하나만 설정하세요.")
    if not raw and not location:
        return Check(name, "MISSING", "서비스 계정 키를 준비한 뒤 JSON 또는 PATH 중 하나를 설정하세요.")
    try:
        if location:
            path = Path(location).expanduser()
            if not path.is_absolute():
                path = root / path
            if not path.is_file():
                return Check(name, "FAIL", "설정한 서비스 계정 키 파일을 찾을 수 없습니다. 경로 내용은 출력하지 않습니다.")
            if path.stat().st_size > 1_000_000:
                return Check(name, "FAIL", "서비스 계정 키 파일 크기가 예상 범위를 초과합니다.")
            raw = path.read_text(encoding="utf-8-sig")
        if len(raw.encode("utf-8")) > 1_000_000:
            return Check(name, "FAIL", "서비스 계정 JSON 크기가 예상 범위를 초과합니다.")
        info = json.loads(raw)
    except (ValueError, OSError, UnicodeError):
        return Check(name, "FAIL", "서비스 계정 JSON을 읽을 수 없습니다. 파일 인코딩과 JSON 형식을 확인하세요.")
    required = ("project_id", "client_email", "private_key", "token_uri")
    if not isinstance(info, dict) or info.get("type") != "service_account" or any(
        not isinstance(info.get(field), str) or not info[field].strip() for field in required
    ):
        return Check(name, "FAIL", "Firebase 웹 설정이 아닌 서비스 계정 JSON이 필요합니다. 필수 필드를 확인하세요.")
    try:
        from firebase_admin import credentials

        credentials.Certificate(info)  # Parses the signing key locally; no network request.
    except Exception:
        # SDK exception text can contain credential material. Do not print it.
        return Check(name, "FAIL", "서비스 계정 필드 또는 서명 키 형식이 올바르지 않거나 Firebase 패키지를 불러올 수 없습니다.")
    return Check(name, "PASS", "JSON·서명 키 형식을 로컬에서 확인했습니다. 실제 프로젝트·DB·권한은 확인하지 않았습니다.")


def check_local_runtime() -> list[Check]:
    checks = [Check("Python", "PASS" if sys.version_info >= (3, 10) else "FAIL",
                    f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} (최소 3.10)")]
    in_venv = sys.prefix != sys.base_prefix
    checks.append(Check("가상환경", "PASS" if in_venv else "FAIL",
                        "프로젝트 전용 환경 사용 중" if in_venv else ".venv의 Python으로 실행하세요."))
    for package, module in PACKAGES.items():
        try:
            importlib.import_module(module)
            version = importlib.metadata.version(package)
            checks.append(Check(package, "PASS", version))
        except Exception:
            checks.append(Check(package, "FAIL", "패키지를 설치하거나 가상환경을 확인하세요."))
    try:
        ZoneInfo("Asia/Seoul")
        checks.append(Check("한국 시간대", "PASS", "Asia/Seoul 로딩 확인"))
    except ZoneInfoNotFoundError:
        checks.append(Check("한국 시간대", "FAIL", "tzdata 패키지가 필요합니다."))
    return checks


def exit_status(checks: list[Check]) -> int:
    if any(check.status == "FAIL" for check in checks):
        return 1
    return 2 if any(check.status == "MISSING" for check in checks) else 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-only", action="store_true", help="Check local tools and non-secret settings only.")
    args = parser.parse_args()
    checks = check_local_runtime()
    try:
        values = read_environment(PROJECT_ROOT / ".env")
    except Exception:
        checks.append(Check("설정 읽기", "FAIL", ".env 파일을 읽을 수 없습니다. 패키지·권한·인코딩을 확인하세요."))
        values = {}
    checks.extend(check_public_settings(values))
    if not args.local_only:
        checks.extend([check_openai_key(values), check_firebase_credentials(values)])
    for check in checks:
        print(f"[{check.status}] {check.name}: {check.message}")
    code = exit_status(checks)
    if code == 0:
        print("로컬 점검 통과. 외부 연결·프로젝트 존재·API 사용 권한을 확인한 결과는 아닙니다.")
    elif code == 2:
        print("로컬 준비는 가능하며, 표시된 외부 설정을 준비해야 합니다. docs/SETUP.md를 확인하세요.")
    else:
        print("설정 오류를 수정한 뒤 다시 실행하세요. 비밀값은 채팅이나 Git에 올리지 마세요.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
