"""LLM과 Kakao Local API를 사용하는 국내 여행 추천 CLI 프로그램."""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, parse, request


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class ApiCallError(Exception):
    """외부 API 호출 또는 응답 처리 중 발생한 오류."""


def load_dotenv(path: Path) -> None:
    """외부 라이브러리 없이 .env 파일의 값을 환경변수에 넣는다."""
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def valid_date(value: str) -> str:
    """YYYY-MM-DD 형식의 실제 날짜인지 검증한다."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("날짜는 YYYY-MM-DD 형식으로 입력하세요.") from exc
    return value


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM 기반 국내 여행 추천 프로그램")
    parser.add_argument(
        "-date",
        "--date",
        required=True,
        type=valid_date,
        help='여행 날짜 (예: "2026-09-15")',
    )
    return parser.parse_args()


def require_api_key(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ApiCallError(
            f"{name} 설정이 필요합니다. .env.example을 참고해 .env 파일 또는 환경변수에 설정하세요."
        )
    return value


def get_codyssey_api_url() -> str:
    """교육기관 API 콘솔에 표시된 Base URL로 OpenAI 호환 엔드포인트를 만든다."""
    base_url = os.getenv("CODYSSEY_API_BASE_URL", "https://copa.codyssey.kr").strip().rstrip("/")
    parsed = parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ApiCallError(
            "CODYSSEY_API_BASE_URL은 http 또는 https URL이어야 합니다. Codyssey API 콘솔의 문서 탭 값을 확인하세요."
        )
    return f"{base_url}/v1/chat/completions"


def require_codyssey_api_key() -> str:
    """새 변수명을 우선 사용하고, 기존 OPENAI_API_KEY도 호환을 위해 허용한다."""
    value = os.getenv("CODYSSEY_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    if not value:
        raise ApiCallError(
            "CODYSSEY_API_KEY 설정이 필요합니다. Codyssey OpenAI 호환 방식으로 발급한 키를 .env에 설정하세요."
        )
    return value


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    api_request = request.Request(url, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(api_request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise ApiCallError(f"HTTP {exc.code}") from exc
    except error.URLError as exc:
        raise ApiCallError(f"네트워크 오류: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ApiCallError("API 응답을 JSON으로 읽을 수 없습니다.") from exc


def get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    api_request = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(api_request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise ApiCallError(f"HTTP {exc.code}") from exc
    except error.URLError as exc:
        raise ApiCallError(f"네트워크 오류: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ApiCallError("API 응답을 JSON으로 읽을 수 없습니다.") from exc


def call_llm(prompt: str, api_key: str) -> str:
    model = os.getenv("CODYSSEY_MODEL", os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "항상 요청한 형식을 지키고, 한국어로 응답하세요."},
            {"role": "user", "content": prompt},
        ],
    }
    response = post_json(
        get_codyssey_api_url(),
        payload,
        {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ApiCallError("LLM 응답에 생성된 텍스트가 없습니다.") from exc


def extract_json(text: str) -> dict[str, Any]:
    """코드 블록이 포함된 LLM 응답에서도 JSON 객체를 추출한다."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ApiCallError("LLM JSON 파싱에 실패했습니다.") from exc
    if not isinstance(value, dict):
        raise ApiCallError("LLM JSON 응답이 객체 형식이 아닙니다.")
    return value


def validate_recommendation(data: dict[str, Any]) -> dict[str, Any]:
    required_types = {"recommended_city": str, "weather": str, "events": list, "reason": str}
    for key, expected_type in required_types.items():
        if not isinstance(data.get(key), expected_type):
            raise ApiCallError(f"LLM JSON의 {key} 값이 올바르지 않습니다.")
    if not all(isinstance(event, str) for event in data["events"]):
        raise ApiCallError("LLM JSON의 events 값이 문자열 목록이 아닙니다.")
    return data


def create_recommendation(date: str, api_key: str) -> dict[str, Any]:
    prompt = f"""여행 날짜는 {date}입니다. 국내 여행 추천 정보를 JSON 객체 하나로만 출력하세요.
필수 키와 타입은 recommended_city(string), weather(string), events(string 배열 1~3개), reason(string, 2~4문장)입니다.
실제 예보가 아닌 해당 시기의 일반적인 날씨와 행사 후보를 제안해도 됩니다. Markdown 코드 블록이나 설명은 포함하지 마세요."""
    retry_prompt = "필수 키 recommended_city, weather, events, reason만 가진 유효한 JSON 객체를 설명 없이 출력하세요.\n" + prompt
    last_error: ApiCallError | None = None
    for current_prompt in (prompt, retry_prompt):
        try:
            return validate_recommendation(extract_json(call_llm(current_prompt, api_key)))
        except ApiCallError as exc:
            last_error = exc
    raise last_error or ApiCallError("여행 추천을 만들지 못했습니다.")


def search_places(city: str, api_key: str) -> list[dict[str, Any]]:
    query = parse.urlencode({"query": f"{city} 맛집", "size": 5})
    response = get_json(f"{KAKAO_KEYWORD_URL}?{query}", {"Authorization": f"KakaoAK {api_key}"})
    documents = response.get("documents", [])
    if not isinstance(documents, list):
        raise ApiCallError("장소 검색 응답 형식이 올바르지 않습니다.")

    places: list[dict[str, Any]] = []
    for place in documents:
        try:
            places.append(
                {
                    "name": place.get("place_name", ""),
                    "address": place.get("road_address_name") or place.get("address_name", ""),
                    "category": place.get("category_name", ""),
                    "url": place.get("place_url", ""),
                    "lat": float(place["y"]),
                    "lng": float(place["x"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return places


def render_fallback_report(date: str, recommendation: dict[str, Any], places: list[dict[str, Any]], errors: list[dict[str, str]]) -> str:
    """최종 LLM 호출 실패 시에도 결과를 남길 수 있는 기본 리포트."""
    events = "\n".join(f"- {event}" for event in recommendation["events"]) or "- 데이터 없음"
    restaurants = "\n".join(
        f"- [{place['name']}]({place['url']}) - {place['address']}" if place["url"] else f"- {place['name']} - {place['address']}"
        for place in places
    ) or "- 데이터 없음"
    error_text = "\n".join(f"- {item['step']}: {item['message']}" for item in errors) or "- 없음"
    return f"""# {date} 국내 여행 추천 리포트

## 추천 지역

{recommendation['recommended_city']}

## 추천 이유

{recommendation['reason']}

## 날씨 요약

{recommendation['weather']}

## 행사/축제

{events}

## 맛집 추천

{restaurants}

## 1일 일정 제안

- 오전: 추천 지역의 주요 명소를 방문합니다.
- 오후: 지역 행사 또는 주변 관광지를 둘러봅니다.
- 저녁: 검색된 맛집에서 식사합니다.

## 오류 요약(errors)

{error_text}
"""


def create_report(date: str, recommendation: dict[str, Any], places: list[dict[str, Any]], errors: list[dict[str, str]], api_key: str) -> str:
    prompt = f"""다음 데이터를 바탕으로 {date} 국내 여행 추천 리포트를 Markdown으로 작성하세요.
반드시 추천 지역, 추천 이유, 날씨 요약, 행사/축제, 맛집 추천, 1일 일정 제안, 오류 요약(errors) 제목을 포함하세요.
맛집 목록이 비어 있으면 맛집 추천에는 '데이터 없음'이라고 쓰세요.

추천 정보: {json.dumps(recommendation, ensure_ascii=False)}
맛집 목록: {json.dumps(places, ensure_ascii=False)}
오류 목록: {json.dumps(errors, ensure_ascii=False)}"""
    try:
        return call_llm(prompt, api_key).strip()
    except ApiCallError as exc:
        errors.append({"step": "report_generation", "type": "LLM_ERROR", "message": str(exc)})
        return render_fallback_report(date, recommendation, places, errors)


def save_results(date: str, recommendation: dict[str, Any], places: list[dict[str, Any]], errors: list[dict[str, str]], report: str) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(exist_ok=True)
    raw_path = RESULTS_DIR / f"{date}_raw_data.json"
    report_path = RESULTS_DIR / f"{date}_travel_plan.md"
    raw_path.write_text(
        json.dumps({"recommendation": recommendation, "places": places, "errors": errors}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path.write_text(report, encoding="utf-8")
    return raw_path, report_path


def main() -> int:
    args = parse_arguments()
    load_dotenv(BASE_DIR / ".env")
    errors: list[dict[str, str]] = []

    try:
        openai_key = require_codyssey_api_key()
    except ApiCallError as exc:
        print(f"오류: {exc}")
        return 1

    print("[1/3] 1차 추천 생성 중(LLM)...")
    try:
        recommendation = create_recommendation(args.date, openai_key)
    except ApiCallError as exc:
        print(f"오류: {exc}")
        return 1
    print(f"  - recommended_city: \"{recommendation['recommended_city']}\"")

    print("[2/3] 맛집 검색 중(지도/장소 API)...")
    places: list[dict[str, Any]] = []
    try:
        kakao_key = require_api_key("KAKAO_REST_API_KEY")
        places = search_places(recommendation["recommended_city"], kakao_key)
        if places:
            print(f"  - 맛집 {len(places)}곳 검색 완료")
        else:
            errors.append({"step": "place_search", "type": "EMPTY_RESULT", "message": f"0 results for query={recommendation['recommended_city']} 맛집"})
            print("  - 검색 결과 0건. 리포트 생성을 계속 진행합니다.")
    except ApiCallError as exc:
        errors.append({"step": "place_search", "type": "API_ERROR", "message": str(exc)})
        print(f"  - 오류: {exc}")
        print("  - 맛집 섹션은 '데이터 없음'으로 처리하고 계속 진행합니다.")

    print("[3/3] 최종 리포트 생성 중(LLM)...")
    report = create_report(args.date, recommendation, places, errors, openai_key)
    raw_path, report_path = save_results(args.date, recommendation, places, errors, report)
    print("  - 리포트 생성 완료")
    print(f"완료! {report_path.relative_to(BASE_DIR)} 를 확인하세요.")
    print(f"원본 데이터: {raw_path.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
