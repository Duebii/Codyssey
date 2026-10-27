# M1-2 · 김실장

**AI Agent 개발: 나만의 AI 비서 구축**

김실장은 작업 기록을 참고해 **무엇부터 할지 정하고, 어떻게 끝낼지 전략을 세우며, 반복 업무의 개선·자동화 방법을 설계하는 AI 업무 전략 비서**입니다. 사용자가 질문할 때 상담을 제공합니다.

## 현재 진행 상태

**10단계 Render·Vercel 배포까지 완료했습니다.** 공개 웹에서 기록 추가·수정, 요약, 실제 GPT 상담·자동 저장, 새로고침 후 이전 상담 불러오기를 확인했습니다. 검증용 기록은 삭제했고 기존 작업 150건·6,524분과 기존 상담 11개를 보존했습니다. Python 221개·Node 14개 테스트를 통과했습니다. [전체 흐름 점검](docs/INTEGRATION.md), [배포 설정과 실제 검증 결과](docs/DEPLOYMENT.md)를 확인할 수 있습니다.

| 접속 | 주소 |
| --- | --- |
| 김실장 웹 | [m1-2-kim-manager.vercel.app](https://m1-2-kim-manager.vercel.app) |
| 백엔드 API 상태 | [Render 서버 상태](https://m1-2-kim-manager.onrender.com/api/health) |
| Swagger API 문서 | [배포 API 문서](https://m1-2-kim-manager.onrender.com/docs) |
| GitHub 코드 | [Duebii/Codyssey · M1-2](https://github.com/Duebii/Codyssey/tree/main/M1-2) |

Render 무료 서버는 오래 사용하지 않으면 첫 접속에 약 1분 걸릴 수 있습니다. 화면에서 서버 준비 안내와 재시도 방법을 확인합니다. 현재는 로그인 없는 가상 데이터 시연용이며, 실제 개인 기록 운영에는 접근 제어를 추가해야 합니다.

서버 실행 중 [김실장 웹 화면](http://127.0.0.1:5500)을 엽니다. [웹 화면 실행·사용 안내](docs/FRONTEND.md)에 두 서버의 실행 방법과 검증 범위를 정리했습니다.

2026-10-27에는 사용자 취향에 맞춰 잉크 블루 중심의 차분한 화면, 한글 서체, 모바일 메뉴와 메모 펼치기를 다듬었습니다. [디자인 기준](docs/UI_DESIGN.md)에 기록했습니다.

| 구분 | 상태 |
| --- | --- |
| 가상 작업 기록 150건 | 완료 |
| 데이터 설명과 분석 예시 | 완료 |
| 재생성·검증 도구 | 완료 |
| 순서별 개발 워크리스트 | 완료 |
| 1단계 화면·상담 규칙·데이터/API 계약 | 설계 완료 |
| 2단계 가상환경·패키지·설정 점검 | 로컬 준비 완료 |
| Firebase 프로젝트·Firestore·서비스 계정 키 | 설정 완료, 실제 150건 저장 및 CRUD 성공 |
| GPT API 키 | 코디세이 제공 키 인증 성공. 코디세이 서버의 `gpt-5-mini` 사용 |
| 3단계 FastAPI 실행·Pydantic 검증·CORS·Swagger | 완료, 외부 키 없이 실행 가능 |
| 4단계 Firestore 연결·작업 CRUD·중복 없는 가져오기 | 완료. 실제 CRUD·중복 방지·서버 재시작 후 유지 확인 |
| 5단계 시계열 분석·요약 API | 완료. Firestore 저장·캐시·CRUD 후 자동 갱신 확인 |
| 6단계 대화 저장·목록·전체 불러오기·삭제 | 완료. 시연용 고정 메시지 4개로 실제 저장·조회·삭제 검증 |
| 7단계 GPT 연동·계획 검증·채팅 자동 저장 | 완료. 전체 테스트 206개·실제 상담 5개 시나리오·재시작 후 대화 유지 확인 |
| 8단계 바닐라 웹 화면 | 완료. 네 화면·실제 API 연결·모바일·빈 상태·오류 안내 확인 |
| 9단계 전체 흐름 점검 | 완료. 기록 CRUD→최신 상담, 90→45분·마감 변경, 이전 상담 재개, 연결 실패·키 노출 검사 |
| 10단계 Render·Vercel 배포 | 완료. 공개 웹·API·Swagger, CORS, 실제 CRUD·GPT·상담 불러오기 검증 |

공유할 코드에는 실제 개인 데이터와 API 키를 포함하지 않습니다. 로컬 `.env`와 서비스 계정 키 파일은 Git에서 제외됩니다. 사용자 승인 후 키는 Render 비공개 환경변수로만 연결했고, Vercel에는 공개 API 주소만 설정했습니다. 배포 시험 후 원본 150건·6,524분과 점검 전 상담 11개의 내용이 그대로임을 확인했습니다. 현재 요약 버전은 168이며, 검증용 상담 2개를 추가해 총 상담 13개·메시지 44개를 보관했습니다. 코디세이 키는 전용 서버로 연결합니다. 더미데이터의 제출 인정 여부는 과제 제공자에게 확인해야 합니다. 실제 업무에서의 효용은 별도 개선 항목으로 남아 있습니다.

## 파일 안내

| 파일 | 용도 |
| --- | --- |
| [WORKLIST.md](WORKLIST.md) | 앞으로 진행할 작업 순서와 단계별 완료 기준 |
| [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md) | 화면 구성·상담 입력과 답변·실행 전략·대표 사용 흐름 |
| [docs/API_CONTRACT.md](docs/API_CONTRACT.md) | 기록·상담 조건의 검증, API 응답, 요약 계산과 최신성 기준 |
| [docs/SETUP.md](docs/SETUP.md) | 로컬 환경 사용법과 남은 Firebase·OpenAI 프로젝트/키 준비 순서 |
| [docs/BACKEND_START.md](docs/BACKEND_START.md) | 외부 키 없이 서버 실행, Swagger 요청 검증, 현재 기능 범위 |
| [docs/FIRESTORE.md](docs/FIRESTORE.md) | 기록 CRUD·트랜잭션·출처 보호·실제 저장/중복/재시작 검증 결과 |
| [docs/SUMMARY.md](docs/SUMMARY.md) | 일별·주별 분석, 예상 시간 비교, 요약 저장·최신성·실제 갱신 검증 |
| [docs/CONVERSATIONS.md](docs/CONVERSATIONS.md) | 대화 API, 목록/상세 분리, 조건·메시지 보존, 실제 저장·조회·삭제 검증 |
| [docs/CHAT.md](docs/CHAT.md) | 코디세이 연결·컨텍스트 주입·계획 검증·호출 제한·실제 상담과 저장 검증 |
| [docs/FRONTEND.md](docs/FRONTEND.md) | 웹 화면 실행·사용법·주소 설정·오류 처리·실제 화면 검증 |
| [docs/INTEGRATION.md](docs/INTEGRATION.md) | 9단계 실제 전체 흐름·발견한 문제와 수정·시험 결과·재현 방법 |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Render·Vercel 설정·환경변수·배포 현황·공개 접속 확인 순서 |
| [docs/UI_DESIGN.md](docs/UI_DESIGN.md) | 네 화면의 디자인과 데이터 표시 기준 |
| [frontend/index.html](frontend/index.html) | 프레임워크 없이 만든 김실장 웹 화면 |
| [scripts/build_frontend.py](scripts/build_frontend.py) | 공개 API 주소만 반영하는 정적 파일 빌드 |
| [scripts/import_dummy_data.py](scripts/import_dummy_data.py) | 기본은 오프라인 검증, 외부 준비 후 명시적으로 더미 기록 가져오기 |
| [.env.example](.env.example) | 비밀값이 비어 있는 설정 예시 |
| [requirements-dev.txt](requirements-dev.txt) | 설치 버전이 고정된 개발 의존성 |
| [scripts/check_environment.py](scripts/check_environment.py) | 값을 출력하거나 외부 호출하지 않는 환경 점검 |
| [docs/DATASET.md](docs/DATASET.md) | 데이터 필드·가상 패턴·분석 기준 설명 |
| [data/work_records.json](data/work_records.json) | 8주 동안의 가상 작업 기록 150건 |
| [data/dataset_metadata.json](data/dataset_metadata.json) | 가상 데이터 표시, 기간, 단위와 생성 조건 |
| [data/summary.preview.json](data/summary.preview.json) | 현재 더미데이터를 분석한 예시 결과 |
| [scripts/generate_dummy_data.py](scripts/generate_dummy_data.py) | 같은 데이터를 재생성하거나 원본 일치 여부 확인 |
| [scripts/verify_dataset.py](scripts/verify_dataset.py) | 데이터와 통계·가상 패턴의 무결성 검증 |

## 로컬 서버 실행

웹 화면용 정적 서버는 별도 터미널에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m http.server 5500 --bind 127.0.0.1 --directory frontend
```

[김실장 웹 화면](http://127.0.0.1:5500)에 접속합니다. 아래 백엔드도 함께 실행돼 있어야 합니다.

외부 프로젝트와 키가 없어도 서버·요청 검증·Swagger를 확인할 수 있습니다. 프로젝트 폴더에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

[Swagger UI](http://127.0.0.1:8000/docs), [서버 상태](http://127.0.0.1:8000/api/health), [데이터 요약 API](http://127.0.0.1:8000/api/data/summary), [대화 목록 API](http://127.0.0.1:8000/api/conversations)를 확인합니다. `AI_PROVIDER=codyssey`로 제공 키를 사용하며, 설정 예시는 현재 검증한 `gpt-5-mini`·출력 6000토큰·요청 60초 기준입니다. 자세한 상담·오류·제공자 선택 방법은 [상담 안내](docs/CHAT.md)를 따릅니다. 키·제공자·모델을 바꾼 뒤에는 서버를 재시작합니다.

더미 기록을 가져오기 전에 외부 연결 없이 파일을 점검할 수 있습니다. 기본 실행은 데이터를 저장하지 않습니다.

```powershell
.\.venv\Scripts\python.exe scripts/import_dummy_data.py
```

## 로컬 개발 환경 점검

이 컴퓨터의 `M1-2/.venv`에는 패키지 설치를 마쳤습니다. 아래 명령은 프로젝트 폴더에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe scripts/check_environment.py --local-only
```

전체 설정 점검은 `--local-only` 없이 실행합니다. 현재 컴퓨터에서는 전체 오프라인 점검을 통과했습니다. 이 점검만으로 OpenAI 호출 성공을 보장하지는 않습니다. 새 환경 설치와 외부 설정은 [환경 준비 안내](docs/SETUP.md)를 따릅니다.

## 더미데이터 확인

Python 3.10 이상에서 실행합니다. 외부 패키지나 API 키는 필요하지 않습니다. 아래 명령은 `M1-2` 폴더에서 실행합니다.

```powershell
python scripts/verify_dataset.py
python scripts/generate_dummy_data.py --check
```

원본 데이터를 다시 생성하려면 다음 명령을 실행합니다. `data/`의 세 JSON 파일이 같은 생성 조건으로 덮어써집니다.

```powershell
python scripts/generate_dummy_data.py
```

## 데이터 개요

- 기간: **2026-08-26 ~ 2026-10-20**, 56일
- 기록: 평일 40일에 걸친 작업 수행 **150건**
- 분야: 프리랜서·취업·창업
- `value`의 의미: 작업 한 건에 실제로 소요된 시간이라는 **가상 설정**, 단위는 분
- 기록이 없는 16일: `unrecorded`로 표시하고 일별 합계는 `null`로 보관
- 시간 기준: 한국 날짜, `Asia/Seoul`

`summary.preview.json`은 시계열 분석을 설명하기 위한 고정된 로컬 예시입니다. 실제 최신 요약은 `/api/data/summary`에서 계산 대상 버전·생성 시각과 함께 조회합니다.

## 기술 구성

- 백엔드: Python · FastAPI · Pydantic
- 저장소: Firebase Firestore
- AI: OpenAI GPT API
- 프론트엔드: HTML/CSS/JavaScript, 프레임워크 미사용
- 배포: Render(백엔드) · Vercel(프론트엔드)

현재 GitHub 업로드와 배포는 수행하지 않았습니다. 단계별 구현 범위는 [워크리스트](WORKLIST.md)를 따릅니다.
