# 10단계 Render·Vercel 배포

2026-10-27 GitHub 업로드와 Render·Vercel 배포를 마쳤고, 실제 공개 웹에서 핵심 사용 흐름을 확인했습니다.

| 항목 | 주소·상태 |
| --- | --- |
| GitHub 코드 | [Duebii/Codyssey · M1-2](https://github.com/Duebii/Codyssey/tree/main/M1-2), 최초 업로드 `70909ad` |
| Render API | [김실장 API](https://m1-2-kim-manager.onrender.com) |
| Swagger | [배포 API 문서](https://m1-2-kim-manager.onrender.com/docs) — 200 확인 |
| Vercel 웹 | [김실장 웹](https://m1-2-kim-manager.vercel.app) — 200 확인 |

Render 작업공간은 사용자가 확인한 `Codyssey`, Vercel은 사용자가 접근을 승인한 `HYO`(`hyo11`)입니다. 비공개 키 2개는 사용자 승인 후 Render 환경변수에만 설정했습니다. Vercel에는 공개 `API_BASE_URL`만 설정했습니다. Python 221개·Node 14개 시험과 공개 파일 키 노출 검사를 통과했습니다.

Vercel 연결 직후 `hyo11` 접근에서 403이 반환됐습니다. 기존 승인 링크는 로그인 중 만료됐고, 로그인된 상태에서 새 링크의 Allow를 사용자가 직접 완료한 뒤 같은 연결로 재조회해 해결했습니다. 배포 프로젝트는 `m1-2-kim-manager`입니다.

## 배포 설정

기존 과제 저장소의 `M1-2`만 빌드합니다. Python은 로컬 검증과 같은 `3.12.14`를 사용합니다. Render 연결 도구는 Root Directory 설정을 지원하지 않아 실제 서비스에서는 빌드·실행 명령의 `cd M1-2`로 작업 위치를 지정했습니다. Blueprint로 새로 구성할 때에는 `rootDir: M1-2`를 사용합니다.

| 설정 | Render 백엔드 | Vercel 프론트 |
| --- | --- | --- |
| 설정 파일 | `M1-2/render.yaml` | `M1-2/vercel.json` |
| 유형 | Python Web Service, Free, Singapore | Other, 정적 파일 |
| Root Directory | 저장소 루트. 명령에서 `M1-2`로 이동 | `M1-2` |
| Build Command | `cd M1-2 && pip install -r requirements.txt` | `python3 scripts/build_frontend.py --production` |
| Start Command | `cd M1-2 && uvicorn main:app --host 0.0.0.0 --port $PORT` | 없음 |
| Output Directory | 해당 없음 | `dist` |
| Health Check | 실제 서비스는 기본 포트 검사. `/api/health`도 200 확인. Blueprint에는 HTTP 검사 지정 | 해당 없음 |
| Install Command | Build Command에 포함 | 비움 (백엔드 패키지 설치하지 않음) |

Render Blueprint를 가져올 경우 경로를 `M1-2/render.yaml`로 지정합니다. 자동 배포는 끄고 변경을 확인한 뒤 수동 배포합니다. Vercel은 `framework: null`로 고정해 같은 폴더의 FastAPI를 자동으로 배포하지 않게 합니다.

## 환경변수

Render에서 다음을 설정합니다. **키는 GitHub·Vercel·프론트 파일에 넣지 않습니다.**

| 이름 | 값 또는 설정 방법 |
| --- | --- |
| `PYTHON_VERSION` | `3.12.14` |
| `APP_ENV` | `production` |
| `AI_PROVIDER` | `codyssey` |
| `OPENAI_MODEL` | `gpt-5-mini` |
| `OPENAI_MAX_OUTPUT_TOKENS` | `6000` |
| `OPENAI_TIMEOUT_SECONDS` | `60` |
| `OPENAI_REASONING_EFFORT` | `omit` |
| `OPENAI_API_KEY` | 현재 검증한 코디세이 제공 키. 비공개 환경변수 |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | 기존 서비스 계정 JSON을 한 줄 JSON으로 설정. 비공개 환경변수 |
| `ALLOWED_ORIGINS` | `https://m1-2-kim-manager.vercel.app,https://m1-2-kim-manager-hyo11.vercel.app` |

Render에는 로컬 전용 `FIREBASE_SERVICE_ACCOUNT_PATH`를 설정하지 않습니다. JSON과 PATH를 동시에 지정하면 연결이 거절됩니다. 백엔드의 `API_BASE_URL`은 따로 지정하지 않으면 Render가 제공하는 `RENDER_EXTERNAL_URL`을 사용합니다. 명시적으로 설정할 경우 실제 Render HTTPS 주소를 넣습니다.

Vercel에는 **`API_BASE_URL` 한 개**만 설정합니다. 값은 실제 Render HTTPS 주소이며 끝에 `/api`를 붙이지 않습니다. Production과 사용할 Preview 환경에 각각 적용합니다. 값을 바꾸면 다시 배포해야 `config.js`가 갱신됩니다.

프론트의 배포 빌드는 API 주소가 없거나 로컬 HTTP 주소이면 실패하도록 했습니다. `dist`에는 허용한 공개 파일 6개만 들어갑니다. 다른 파일이 남아 있으면 배포 빌드를 중단하므로 내용을 확인해 별도로 보관한 뒤 다시 실행합니다.

## 접속 확인 순서

1. Render 배포 로그에서 실행 성공과 실제 URL을 확인합니다.
2. API의 `/api/health`, `/docs`, `/api/data/summary`, `/api/conversations`를 확인합니다. Health는 서버 기동 확인이며 GPT·Firestore 연결 성공을 뜻하지 않습니다.
3. Vercel의 `API_BASE_URL`로 Render 주소를 설정하고 배포합니다.
4. 실제 Vercel 주소를 Render의 `ALLOWED_ORIGINS`에 적용해 다시 배포합니다.
5. Vercel 화면에서 요약·목록·이전 대화를 불러옵니다.
6. 이름으로 구분한 검증용 가상 기록 한 건만 추가·수정·삭제하고 최신 요약을 비교합니다. 기존 기록은 변경하지 않습니다.
7. 실제 GPT 질문 한 번의 로딩·답변·자동 저장을 확인한 뒤 새로고침하고 불러옵니다. 성공·저장 여부가 불확실하면 이전 상담을 먼저 확인하고 유료 요청을 반복하지 않습니다.
8. 허용한 Vercel 주소의 CORS 사전 요청이 성공하고, 미허용 주소에는 허용 헤더가 없는지 확인합니다.

## 첫 접속 지연과 운영 범위

Render 무료 Web Service는 15분간 요청이 없으면 정지하며 다시 깨어날 때 약 1분 걸릴 수 있습니다. 화면에는 서버 준비 안내·재시도·질문 보존을 제공하고, 채팅·저장 요청은 자동 재전송하지 않습니다. 지연된 저장이 이미 완료됐을 수 있으므로 목록·이전 상담을 확인합니다.

현재 앱은 가상 데이터를 사용하는 단일 사용자 과제 시연용입니다. 로그인·사용자별 데이터 분리는 후속 범위입니다. 공개 주소를 아는 사람은 공개 API로 기록·상담을 읽거나 변경할 수 있으며 CORS는 인증을 대신하지 않습니다. 실제 개인 업무 기록을 운영하기 전에는 접근 제어를 추가해야 합니다. 상담 호출 제한과 일일 시도 상한은 서버 프로세스 기준이며 재시작 시 초기화됩니다.

## 실제 배포 검증 결과

| 확인 항목 | 결과 |
| --- | --- |
| Render 실행·Swagger·Firestore | `/api/health`, `/docs`, `/api/data/summary` 200. 150건·6,524분 |
| 배포 API의 CRUD | 임시 기록 11분 추가 → 19분 수정 → 삭제. 151건·6,535분 → 151건·6,543분 → 150건·6,524분, 요약 v162→165 |
| 실제 GPT 연결 | API에서 질문 1회·응답·메시지 2개 자동 저장 확인 |
| Vercel 정적 빌드 | GitHub `M1-2`를 Other로 빌드, `config.js`가 실제 Render 주소를 포함. 공개 웹과 설정 파일 200 |
| 실제 웹의 채팅 | 공개 웹에서 질문 1회·로딩·150건/6,524분 답변·자동 저장 확인 |
| 실제 웹의 기록 관리 | 임시 기록 12분 추가 → 18분 수정. 이름·날짜·신규 ID가 일치하는 시험 기록만 API로 삭제. 요약 v165→168 |
| 상담 불러오기 | 공개 웹 새로고침 → 이전 상담 13개 목록 → 방금 저장한 상담의 질문·답변·종류 복원 |
| CORS | 실제 Vercel 주소 2개는 OPTIONS 200·정확한 허용 origin. 미허용 주소는 400·허용 헤더 없음 |
| 기존 데이터 보존 | 작업 150건 전체 내용과 기존 상담 11개 전체 내용을 점검 전후 해시 비교. 변경 없음 |
| 최종 저장 상태 | 150건·6,524분·요약 v168, 상담 13개·메시지 44개. 새 검증용 상담 2개는 보관 |

Render는 Free 서비스이며 자동 코드 배포를 끈 상태입니다. 환경변수 갱신 시 새 배포가 만들어질 수 있으므로 배포 목록을 확인합니다. Vercel의 Git 연결은 `Duebii/Codyssey`의 `main`, Root Directory는 `M1-2`입니다. 이 폴더 변경이 푸시되면 자동 배포될 수 있습니다.

과금이 발생할 수 있는 실제 GPT 시험은 총 2회로 제한했습니다. 첫 접속 지연·요청 제한 안내와 자동 재전송 방지는 코드와 자동 시험으로 확인했고, 무료 서버를 15분간 일부러 정지시키거나 유료 요청으로 한도를 소진하는 시험은 하지 않았습니다.

| 공개 웹 캡처 | 내용 |
| --- | --- |
| [질문·답변과 요약](screenshots/stage10-20261027/chat-restored.jpg) | 실제 GPT 상담을 새로고침 후 다시 불러온 화면 |
| [기록 수정](screenshots/stage10-20261027/records-update.jpg) | 정리 전 시험 기록 18분·151건이 표시된 화면 |
| [이전 상담](screenshots/stage10-20261027/history.jpg) | 새로고침 후 상담 목록에서 불러오기 직전 |

## 공식 안내

- [Render FastAPI 배포](https://render.com/docs/deploy-fastapi), [Blueprint 설정](https://render.com/docs/blueprint-spec), [Python 버전](https://render.com/docs/python-version)
- [Render 제공 환경변수](https://render.com/docs/environment-variables), [무료 서비스의 접속 지연](https://render.com/docs/free)
- [Vercel 설정 파일](https://vercel.com/docs/project-configuration/vercel-json), [빌드 환경](https://vercel.com/docs/builds/build-image), [하위 폴더 배포](https://vercel.com/docs/monorepos)
