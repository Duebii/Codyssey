# 국내 여행 추천 프로그램

여행 날짜를 입력하면 Codyssey 교육기관 API가 국내 여행 지역·날씨·행사 정보를 추천하고, Kakao Local API가 해당 지역의 맛집을 검색한 뒤, 최종 여행 리포트를 만드는 CLI 프로그램입니다.

외부 라이브러리 없이 Python 표준 라이브러리만 사용합니다.

## 기능

- `-date` 또는 `--date`로 여행 날짜 입력
- 날짜 형식 검증
- LLM으로 추천 지역, 날씨, 행사·축제, 추천 이유 생성
- LLM JSON 파싱 실패 시 최대 1회 재시도
- Kakao Local API로 추천 지역 맛집 최대 5곳 검색
- 장소 검색 실패 또는 0건이어도 리포트 생성 계속 진행
- 원본 데이터 JSON과 최종 Markdown 리포트 저장

## 실행 환경

- Python 3.10 이상
- Codyssey OpenAI 호환 API 키
- Codyssey API Base URL
- Kakao REST API 키

## API 키 설정

`.env.example`을 참고해 `A1-2` 폴더에 `.env` 파일을 만들고 키를 설정합니다. Codyssey 공개 API의 기본 Base URL은 `https://copa.codyssey.kr`이며, 다른 환경을 사용할 때만 `CODYSSEY_API_BASE_URL` 값을 변경합니다.

```text
CODYSSEY_API_BASE_URL="https://copa.codyssey.kr"
CODYSSEY_API_KEY="YOUR_CODYSSEY_API_KEY"
KAKAO_REST_API_KEY="YOUR_KAKAO_REST_API_KEY"
```

또는 현재 터미널 세션의 환경변수로 설정할 수 있습니다.

```powershell
$env:CODYSSEY_API_BASE_URL="https://copa.codyssey.kr"
$env:CODYSSEY_API_KEY="YOUR_CODYSSEY_API_KEY"
$env:KAKAO_REST_API_KEY="YOUR_KAKAO_REST_API_KEY"
```

`.env` 파일은 `.gitignore`에 포함되어 있으므로 Git에 커밋하지 않습니다. 실제 API 키를 README, 소스 코드, 실행 로그, 결과 파일에 작성하지 마세요.

선택적으로 `CODYSSEY_MODEL` 환경변수에 Codyssey API 콘솔 문서 탭에서 지원하는 GPT 모델명을 설정할 수 있습니다.

## 실행 방법

`A1-2` 폴더에서 다음 명령을 실행합니다.

```powershell
python travel_planner.py --date "2026-09-15"
```

잘못된 날짜를 입력하면 사용법이 출력됩니다.

```powershell
python travel_planner.py --date "2026-02-30"
```

## 결과 확인

성공적으로 실행하면 `results/` 폴더에 날짜별 파일이 만들어집니다.

```text
results/
├── 2026-09-15_raw_data.json
└── 2026-09-15_travel_plan.md
```

- 원본 JSON: 1차 추천 결과, 맛집 검색 결과, 오류 목록
- Markdown 리포트: 추천 지역, 추천 이유, 날씨, 행사·축제, 맛집, 1일 일정, 오류 요약

## 테스트

API 키 없이 동작하는 날짜 검증·JSON 파싱·기본 리포트 생성 테스트는 다음 명령으로 실행합니다.

```powershell
python -m unittest test_travel_planner.py
```
