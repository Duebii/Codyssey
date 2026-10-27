# 김실장 · 2단계 개발 환경과 설정 준비

## 현재 상태

**로컬 환경과 Firebase 키 연결을 마쳤고, 더미데이터 150건 저장·실제 CRUD·중복 방지·서버 재시작 후 유지를 확인했습니다.**

| 항목 | 상태 | 확인 범위 |
| --- | --- | --- |
| Python 3.12.14와 프로젝트 `.venv` | 완료 | 실제 실행 확인. 미션의 최소 조건은 Python 3.10 이상 |
| FastAPI·Uvicorn·Firebase Admin·OpenAI·python-dotenv | 완료 | 설치와 가져오기 확인 |
| Pydantic·한국 시간대 자료 | 완료 | 모델 패키지, `Asia/Seoul` 로딩 확인 |
| pytest·httpx와 버전 목록 | 완료 | 테스트 실행, 의존성 충돌 점검 |
| `.env.example`과 로컬 `.env` | 완료 | 예시는 비밀값이 비어 있음. 실제 `.env`와 `.secrets/`는 Git 제외 |
| 설정 점검 도구 | 완료 | 잘못된 입력·키 비노출·환경변수 우선순위 검증 |
| GitHub·Firebase·OpenAI API·Render·Vercel 계정 | 사용자 보유 확인 | 사용자가 계정 보유를 알려줌. 로그인 상태를 직접 점검한 것은 아님 |
| Firebase 프로젝트 | 생성 확인 | 2026-10-21 Firebase 콘솔에서 `M1-2 Mr kim` (`m1-2-mr-kim`) 확인 |
| Firestore Database | 실제 저장·CRUD 확인 | `(default)`, `asia-northeast3`. 2026-10-21 작업 기록 150건·6,524분, 중복 방지·재시작 후 유지 확인 |
| Firebase 서비스 계정 키 | 설정 완료 | 사용자 승인 후 발급한 파일을 `.secrets/firebase-service-account.json`에 보관하고 `.env`의 경로에 연결. 프로젝트·계정·서명 키와 실제 읽기 확인 |
| GPT API 키(코디세이 제공) | 실제 인증·상담 성공 | 2026-10-22 코디세이 전용 서버의 `gpt-5-mini`로 실제 상담·자동 저장·재시작 후 유지 확인 |

가상환경이나 패키지는 GitHub에 올리지 않습니다. 서버 기반과 Firestore CRUD·GPT를 실제로 검증했고 8단계 웹 화면까지 연결했습니다. 실행 방법과 결과는 [로컬 서버 안내](BACKEND_START.md), [Firestore 안내](FIRESTORE.md), [웹 화면 안내](FRONTEND.md)에 정리했습니다.

## 1. 로컬 환경 사용

아래 명령은 `M1-2` 폴더에서 실행합니다. 가상환경을 활성화하지 않아도 해당 Python을 직접 지정해 사용할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe scripts/check_environment.py --local-only
```

현재 컴퓨터에는 설치가 완료되어 있습니다. 새 컴퓨터에서 재현할 때는 다음 순서로 준비합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

`.python-version`에는 이번에 검증한 Python 3.12.14를 기록했습니다. 이 파일 자체가 Python을 설치하거나 전환하지는 않습니다. 다른 Python 버전과 Render의 Linux 환경은 배포 단계에서 별도로 확인합니다.

### 의존성 파일

| 파일 | 사용 목적 |
| --- | --- |
| `requirements.txt` | 런타임 패키지와 하위 의존성의 설치 버전 고정 |
| `requirements-dev.txt` | 위 런타임에 테스트 도구 버전을 추가. 로컬 개발 시 설치 |
| `requirements.in` | 런타임 업데이트 검토용 직접 의존성 범위 |
| `requirements-dev.in` | 개발용 업데이트 검토 범위 |

설치에는 버전이 고정된 `.txt` 파일을 사용합니다. `.in`은 의도적으로 버전을 갱신할 때 검토하는 파일입니다. `httpx`는 HTTP 테스트 도구이며, 현재 Firebase/OpenAI 하위 의존성으로도 설치됩니다.

## 2. 환경변수 입력 위치

로컬 `.env`는 `.env.example`에서 비밀값이 없는 상태로 생성했습니다. 기존 `.env`가 있을 때는 덮어쓰지 않습니다.

| 변수 | 용도 | 현재 상태·검증 |
| --- | --- | --- |
| `APP_ENV` | `development` 또는 `production` | 로컬은 `development` |
| `AI_PROVIDER` | 키를 발급한 제공자 선택 | 현재 `codyssey`. 개인 OpenAI Platform 키를 쓸 때는 `openai` |
| `OPENAI_API_KEY` | 선택한 제공자의 GPT 호출 인증 | 코디세이 키 실제 인증·사용 확인. 비공개 `.env`에만 보관 |
| `OPENAI_MODEL` 등 상담 설정 | 모델·출력 토큰·시간 제한 | 현재 `gpt-5-mini`, 6000토큰, 60초, 추론 옵션 `omit`. [전체 변수](CHAT.md) |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | 로컬 서비스 계정 JSON 파일 경로 | `.secrets/firebase-service-account.json` 설정 및 실제 읽기 확인 |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | 배포 등에서 JSON 전체를 환경변수로 제공 | 미입력. 로컬 파일 경로와 동시에 설정하지 않음 |
| `ALLOWED_ORIGINS` | API를 호출할 프론트엔드 출처 목록 | `http://localhost:5500,http://127.0.0.1:5500` |
| `API_BASE_URL` | 프론트엔드가 사용할 공개 백엔드 주소 | 로컬 `http://127.0.0.1:8000`. 정적 화면에는 `config.js`로 반영. 서버는 별도 실행 |

주소에는 인증 정보·쿼리·와일드카드를 넣지 않습니다. 허용 출처에는 경로나 마지막 `/`도 넣지 않습니다. API 기본 주소에는 `/api`를 붙이지 않습니다. 로컬 개발의 루프백 주소만 HTTP를 허용하고 배포 환경은 HTTPS를 사용합니다.

### 읽기 순서와 오류 처리

1. 프로젝트 루트의 `.env`를 명시적으로 읽습니다.
2. 운영체제·배포 플랫폼의 환경변수가 있으면 `.env`보다 우선합니다. 명시적인 빈 값도 우선합니다.
3. `.env` 문자열의 `${...}` 보간을 수행하지 않아 인증 문자열이 의도치 않게 바뀌지 않도록 합니다.
4. 필수 항목 누락은 `MISSING`, 잘못된 형식은 `FAIL`로 표시합니다. 실제 키·JSON·파일 경로와 SDK 오류 전문은 출력하지 않습니다.
5. 앱의 실제 설정 로더와 시작 시 오류 처리는 3단계에서 이 기준을 이어받아 구현합니다.

이 방식의 점검은 `scripts/check_environment.py`로 검증합니다. 서비스 계정은 JSON 구조와 서명 키 형식까지 로컬에서 파싱하지만, 계정이 실제로 존재하거나 접근 권한이 있다는 것을 보증하지 않습니다.

## 3. Firebase 설정 방법과 현재 완료 상태

### 프로젝트와 Firestore

1. [Firebase 콘솔](https://console.firebase.google.com/)에 로그인합니다.
2. 현재 프로젝트는 `M1-2 Mr kim`, 프로젝트 ID는 `m1-2-mr-kim`입니다. 2026-10-21 콘솔에서 확인했습니다. 새 환경에서 진행할 때는 본인의 미션용 프로젝트를 사용합니다.
3. 프로젝트의 Firestore 메뉴에서 데이터베이스를 생성합니다. 첫 버전은 **Standard edition, 기본 `(default)` 데이터베이스**를 대상으로 합니다.
4. 현재 `(default)` 데이터베이스의 위치는 `asia-northeast3`입니다. 2026-10-21 콘솔에서 생성 상태와 빈 데이터베이스를 확인했습니다. 새 환경에서는 콘솔의 선택지와 이후 백엔드 위치를 함께 보고 선택합니다.
5. 서버의 Admin SDK로 접근하는 구조이므로 시작 보안 규칙은 **프로덕션 모드**를 사용합니다. 인증된 서버 접근 권한은 별도로 적용됩니다. [Firestore 공식 시작 안내](https://firebase.google.com/docs/firestore/quickstart)

### 서비스 계정 키

1. 프로젝트 설정의 **서비스 계정** 탭으로 이동합니다.
2. 새 비공개 키를 생성해 JSON 파일을 로컬에 보관합니다. [Firebase Admin 공식 설정 안내](https://firebase.google.com/docs/admin/setup)
3. `M1-2/.secrets/` 폴더를 만들고 파일을 `firebase-service-account.json` 이름으로 보관합니다. 이 폴더는 Git에서 제외됩니다.
4. 로컬 `.env`에서 다음 경로를 설정하고 `FIREBASE_SERVICE_ACCOUNT_JSON`은 비워 둡니다.

```dotenv
FIREBASE_SERVICE_ACCOUNT_PATH=.secrets/firebase-service-account.json
FIREBASE_SERVICE_ACCOUNT_JSON=
```

`FIREBASE_SERVICE_ACCOUNT_PATH`와 `FIREBASE_SERVICE_ACCOUNT_JSON`은 이 프로젝트가 읽기로 정한 변수입니다. SDK가 자동으로 읽는 변수라는 뜻은 아닙니다. 4단계에서 실제 SDK 초기화를 구현했고, 2026-10-21 키 설정과 서버 읽기를 확인했습니다.

웹 앱에 표시되는 Firebase 설정값과 서버의 서비스 계정 JSON은 서로 다릅니다. JSON 키는 브라우저·스크린샷·채팅·Git에 넣지 않습니다.

## 4. 남은 외부 준비: OpenAI API

1. [OpenAI API 플랫폼](https://platform.openai.com/)에 로그인하고 김실장에 사용할 프로젝트를 준비합니다.
2. 해당 프로젝트의 API 키를 발급합니다.
3. 실제 값은 로컬 `.env`의 `OPENAI_API_KEY`에 입력합니다. 문서나 채팅에는 붙여넣지 않습니다.
4. 키 유효성·API 사용 권한·이용 한도는 이후 실제 호출 단계에서 확인합니다. 이번 환경 점검은 요청을 보내거나 API 비용을 발생시키지 않습니다.

OpenAI Docs는 Python SDK와 환경변수·`.env`를 통한 키 관리를 안내합니다. [공식 Python SDK 문서](https://developers.openai.com/api/reference/python)

모델 선택과 응답 토큰·요청 제한은 [7단계 상담 안내](CHAT.md)에 정리했습니다. Render에는 백엔드 비밀값을 설정하고, Vercel에는 공개 `API_BASE_URL`만 전달합니다. 로컬 `.env` 전체를 프론트 설정으로 복사하지 않습니다.

GitHub·Render·Vercel 계정은 보유 상태로 기록했습니다. 저장소 연결과 실제 서비스 생성·배포는 10단계에서 진행합니다.

## 5. 점검 명령과 결과 해석

### 로컬 준비만 확인

```powershell
.\.venv\Scripts\python.exe scripts/check_environment.py --local-only
```

외부 키가 없어도 로컬 도구·한국 시간대·공개 설정이 준비돼 있으면 통과합니다.

### 외부 인증 정보의 입력 여부도 확인

```powershell
.\.venv\Scripts\python.exe scripts/check_environment.py
```

| 종료 코드 | 의미 |
| --- | --- |
| `0` | 요청한 오프라인 점검 통과. 외부 연결 성공 의미는 아님 |
| `1` | 패키지·설정·인증 정보 형식 오류가 있음 |
| `2` | 확인한 항목에 형식 오류는 없으나 필수 설정이 비어 있음 |

2026-10-21 전체 오프라인 설정 점검은 **모든 항목 `PASS`, 종료 코드 0**을 확인했습니다. 2026-10-22 코디세이 제공 키를 전용 서버로 연결해 실제 인증·상담·자동 저장을 확인했습니다. 형식 점검과 실제 외부 요청은 별도 검증입니다. 코디세이 키를 OpenAI 공식 서버로 보내는 설정은 맞지 않습니다.

### 의존성과 설정 검사 테스트

```powershell
.\.venv\Scripts\python.exe -m pip check
New-Item -ItemType Directory -Path .tmp -Force | Out-Null
.\.venv\Scripts\python.exe -m pytest --basetemp=.tmp/pytest
```

테스트는 외부 서비스를 호출하지 않습니다. 환경변수 우선순위, 잘못된 주소·JSON·키, 비밀값 비노출, 임시 생성한 서명 키 파싱을 확인합니다. 임시 파일은 Git에서 제외된 `.tmp/` 안에만 둡니다. 위 테스트는 반드시 `M1-2` 폴더에서 실행합니다.

## 6. 2단계 완료를 위한 남은 확인

- [x] 로컬 개발 환경과 버전 목록 준비.
- [x] 설정 예시·로컬 빈 설정·점검 도구·오류 안내 준비.
- [x] 사용자 계정 보유 상태 기록.
- [x] Firebase 프로젝트 생성 확인 (`m1-2-mr-kim`).
- [x] Firestore 생성 확인 (`(default)`, `asia-northeast3`).
- [x] 서버에서 Firestore 실제 읽기·쓰기·수정·삭제 확인. 현재 150건이며 중복 방지·재시작 후 유지 확인.
- [x] 서비스 계정 키를 로컬에 보관하고 설정. `.env`·키 파일 Git 제외 확인.
- [x] GPT API 키 입력·기본 형식 확인 (실제 키 값 비공개).
- [x] 코디세이 제공 키의 인증·GPT 모델·실제 사용 가능 여부 확인 (7단계 실제 호출).
- [x] 전체 오프라인 설정 점검에서 미입력 항목 해소.

설정 준비와 실제 외부 사용 확인을 마쳤습니다. [워크리스트](../WORKLIST.md)에 같은 상태를 반영합니다. Render·Vercel 프로젝트 생성과 배포는 10단계에서 진행합니다.
