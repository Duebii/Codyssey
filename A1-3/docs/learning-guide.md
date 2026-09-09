# 내가 RE:ST 코드를 설명하는 방법

## 1. HTML, CSS, JavaScript의 역할

**HTML은 화면에 무엇이 있는지 정의합니다.** `index.html`에는 제목, 메뉴, 코스 라디오 버튼, 입력 폼, 재생 버튼, 오디오 요소가 있습니다. 이미지에 찍힌 버튼을 클릭하는 것이 아니라 실제 `<a>`, `<button>`, `<input>`을 사용합니다.

**CSS는 어떻게 보일지 정합니다.** `css/style.css`의 `:root`에는 베이지·갈색·올리브 같은 공통 색상이 있습니다. 데스크톱에서는 사진과 폼을 두 열로, 모바일에서는 위아래로 배치합니다. `@media`가 화면 폭을 보고 적용할 스타일을 고릅니다. 원본에 이미 있는 글씨는 SVG의 `viewBox`로 해당 영역을 보이지 않게 하여 HTML 글씨와 겹치지 않게 했습니다.

**JavaScript는 행동에 반응합니다.** `js/app.js`는 버튼 클릭을 듣고 화면을 바꾸거나 음악을 재생합니다. 폼 값을 읽고 서버에 보내며, 응답을 받아 코스명과 이유를 표시합니다.

## 2. 메뉴를 누르면 어떤 일이 생기나요?

About 링크를 누르면 주소의 끝이 `#about`이 됩니다. JavaScript의 `hashchange` 이벤트가 이를 감지합니다. `renderRoute()`는 About의 `hidden`을 해제하고 다른 화면을 숨깁니다. 전체 페이지를 새로 받지 않으므로 화면 전환이 가볍고, 브라우저 뒤로 가기로 이전 화면으로 돌아갈 수 있습니다.

이때 화면에 없는 버튼이 키보드로 선택되지 않도록 `hidden`을 사용합니다. 호흡 화면을 떠나면 `pauseSession()`을 호출해 음악을 멈춥니다.

## 3. 음악과 타이머는 어떻게 연결되나요?

`courses` 객체에는 세 코스의 ID, 이름, MP3 경로가 있습니다. `chooseCourse()`가 고른 ID에 맞춰 `<audio>`의 `src`를 설정합니다. 재생은 명시적인 **호흡 시작** 버튼을 눌렀을 때 `audio.play()`로 시작합니다.

- `audio.pause()`: 음악을 멈춥니다.
- `audio.currentTime = 0`: 파일의 처음으로 이동합니다.
- `audio.loop = true`: HTML의 `loop` 속성으로 짧은 음원을 반복합니다.
- `elapsedMs`: 일시정지 전까지 실제로 흐른 시간을 보관합니다.
- `startedAt`: 재생을 시작한 순간을 기록합니다.
- `performance.now() - startedAt`: 이번 재생 중 흐른 시간입니다.

단순히 ‘타이머가 한 번 호출될 때마다 1초 더하기’를 하면 브라우저가 바쁠 때 오차가 누적됩니다. 여기서는 실제 시간 차이를 읽어 계산합니다. 일시정지 중에는 시간이 늘지 않습니다. 180초가 되면 `completeSession()`이 음악을 멈추고 완료 화면을 엽니다.

Web Audio의 GainNode는 음량을 조절하는 장치입니다. 하나는 사용자가 선택한 음량에, 하나는 마지막 0.5초의 부드러운 음량 감소와 3분 종료 예약에 씁니다. 따라서 일반 화면 타이머가 느려져도 오디오 엔진이 예정된 시각에 소리를 줄일 수 있습니다.

## 4. 사용자 입력이 fetch로 바뀌는 과정

1. 사용자가 환경·상황·필요한 도움을 입력하고 제출합니다.
2. `submit` 이벤트에서 `event.preventDefault()`로 기본 새로고침을 막습니다.
3. `new FormData(careForm)`가 입력 값을 읽습니다.
4. 공백을 정리하고 필수값·문자 수를 검사합니다. 빠진 값이 있으면 여기서 멈춥니다.
5. `JSON.stringify(payload)`가 JavaScript 객체를 네트워크로 보낼 JSON 문자열로 바꿉니다.
6. `fetch('/api/recommend', { method: 'POST', ... })`가 같은 사이트의 Python API에 보냅니다.
7. 응답을 `response.json()`으로 읽고 HTTP 상태와 내용을 확인합니다.
8. 정상일 때 `textContent`로 결과를 표시합니다. HTML로 실행하지 않고 글자로 보여주기 때문에 결과에 태그가 들어 있어도 실행되지 않습니다.

브라우저 코드에는 API 키도, 실제 추천인 척하는 임시 결과도 없습니다.

## 5. Python Serverless Function은 무엇을 하나요?

`api/recommend.py`는 화면 뒤에서 요청을 처리합니다. 브라우저가 POST를 보내면 `handler.do_POST()`가 실행됩니다. JSON을 읽고 필수값·길이를 다시 확인한 다음 `call_ai()`가 OpenAI에 HTTPS 요청을 보냅니다.

AI는 JSON Schema에 따라 ID와 이유를 반환하지만, 서버는 이를 그대로 믿지 않고 `extract_recommendation()`과 `validate_recommendation()`으로 재검사합니다. 세 ID 중 하나가 아니거나 이유가 비어 있으면 502 오류를 보냅니다. 한국어 코스명은 서버의 `COURSES`에서 결정합니다.

Vercel에서는 요청이 들어올 때 실행 환경이 함수를 처리하므로 개인 컴퓨터에 서버 터미널을 계속 켜놓을 필요가 없습니다. 로컬 `dev_server.py`는 같은 API 코드를 내 컴퓨터의 HTTP 서버에서 실행하도록 연결해 줍니다.

## 6. API 키를 환경 변수로 관리하는 이유

브라우저가 받는 HTML과 JavaScript는 누구나 개발자 도구로 읽을 수 있습니다. 키를 거기에 넣으면 다른 사람이 복사할 수 있습니다. 서버만 읽을 수 있는 환경 변수에 넣으면 키를 화면으로 전달하지 않고 OpenAI 인증에 사용할 수 있습니다.

로컬에서는 `.env`를 서버가 읽습니다. Git은 이 파일을 무시하고, 로컬 서버도 HTTP로 이 파일을 제공하지 않습니다. 배포 환경에서는 Vercel의 Environment Variables가 같은 역할을 합니다. 실제 키는 코드나 대화에 넣지 않습니다.

## 7. 로컬과 Vercel의 차이

| 로컬 | Vercel |
| --- | --- |
| 내 컴퓨터의 `python dev_server.py` | Vercel 서버의 Python Function |
| `http://localhost:3000` | 배포 후 확인되는 HTTPS 공개 URL |
| `.env`에서 키 읽기 | Vercel 프로젝트 환경 변수에서 키 읽기 |
| 터미널을 켜두어야 함 | Vercel이 서버 운영 |
| 수정 후 새로고침, Python 수정 시 서버 재시작 | GitHub 변경으로 재배포 후 반영 |
| 로그는 터미널 | 로그는 Vercel Deployments / Functions |

화면 코드와 `/api/recommend`의 요청·응답 형식은 두 환경에서 같습니다. Vercel의 Root Directory를 `A1-3`로 맞추는 것이 중요합니다.

## 8. 오류가 나면 어디부터 볼까요?

1. **화면이 안 열리면** 서버 터미널이 켜져 있는지, 주소와 포트가 맞는지 확인합니다.
2. **음악이 안 나오면** 시작 버튼을 눌렀는지, 음소거·기기 음량, Network에서 MP3 요청 성공 여부를 확인합니다.
3. **버튼이 안 움직이면** 브라우저 F12 → Console에서 JavaScript 오류를 확인합니다.
4. **추천이 안 나오면** F12 → Network → `recommend` → Status / Response를 봅니다.
5. **503 NOT_CONFIGURED이면** `.env` 또는 Vercel 환경 변수를 확인하고 재시작·재배포합니다.
6. **AI_AUTH_ERROR이면** 서버에 설정한 키가 유효한지, 해당 프로젝트의 사용 권한을 확인합니다.
7. **429이면** API 사용 한도·결제 상태를 확인하고 잠시 후 다시 시도합니다.
8. **502 / 504이면** 터미널 또는 Vercel Function Logs의 오류 코드와 요청 ID를 확인합니다.

로그는 오류 종류를 찾기 위한 것입니다. 키나 입력 전체를 `print()` / `console.log()`에 추가하지 않습니다.

## 9. 수정 후 GitHub와 Vercel에 반영되는 과정

파일 수정 → 로컬 실행·테스트 → A1-3 파일만 `git add` → `git commit`으로 변경 기록 → `git push`로 GitHub 업로드 → PR 검토·병합 → 연결된 Vercel이 운영 브랜치를 배포 → 공개 주소 확인 순서입니다.

커밋은 내 컴퓨터의 저장 기록, push는 GitHub 업로드, deploy는 사용자에게 보이는 사이트 반영입니다. 서로 다른 단계이므로 로컬에서 수정했다고 공개 사이트가 곧바로 바뀌지 않습니다. 자세한 명령과 로그인 순서는 [설정·배포 안내](setup-and-deploy.md)에 있습니다.
