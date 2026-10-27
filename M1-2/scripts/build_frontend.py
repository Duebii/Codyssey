"""Prepare the vanilla frontend with one public environment variable; no secrets."""
import argparse
import json
import os
from pathlib import Path
from shutil import copyfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ("index.html", "styles.css", "app.js", "lib.js", "mark.svg")


def validate_api_url(value: str, *, production: bool = False) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or any(ch in value for ch in '<>"\r\n')
        or parsed.path not in {"", "/"}
        or any(ch.isspace() for ch in value)
        or (parsed.scheme == "http" and (production or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}))
    ):
        raise ValueError("API_BASE_URL에는 공개 HTTPS 서버 주소 또는 로컬 HTTP 주소만 넣으세요. 인증 정보는 넣지 않습니다.")
    return value.rstrip("/")


def build(*, production: bool = False) -> None:
    if production and not os.environ.get("API_BASE_URL"):
        raise ValueError("Vercel의 API_BASE_URL에 실제 Render HTTPS 주소를 설정하세요.")
    api_url = validate_api_url(os.environ.get("API_BASE_URL", "http://127.0.0.1:8000"), production=production)
    output = ROOT / "dist"
    allowed = {*ASSETS, "config.js"}
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(
        path.is_symlink() or path.name not in allowed or not path.is_file() for path in output.iterdir()
    ))):
        raise ValueError("dist에 배포 대상 외 파일이 있습니다. 내용을 확인한 뒤 별도로 보관하고 다시 빌드하세요.")
    output.mkdir(exist_ok=True)
    for asset in ASSETS:
        copyfile(ROOT / "frontend" / asset, output / asset)
    config = json.dumps({"API_BASE_URL": api_url}, ensure_ascii=True)
    (output / "config.js").write_text(f"// Public configuration only.\nwindow.KIM_CONFIG = Object.freeze({config});\n", encoding="utf-8")
    print("Frontend ready: dist/ (6 public files, no credentials)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", action="store_true", help="Require an explicit public HTTPS backend URL")
    build(production=parser.parse_args().production)
