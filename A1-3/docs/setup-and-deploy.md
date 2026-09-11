# API 키 설정부터 GitHub·Vercel 배포까지

지금은 로컬 화면·음악·서버를 사용할 수 있습니다. 아래 계정 설정은 원할 때 직접 진행하면 됩니다. **API 키와 비밀번호는 대화·코드·스크린샷에 입력하지 않습니다.** 실제 키는 내 컴퓨터의 `.env`와 Vercel 환경 변수 입력란에만 넣습니다.

## 1. 먼저 로컬 사이트 열기

1. PowerShell 또는 VS Code 터미널을 엽니다.
2. 다음을 한 줄씩 실행합니다.

   ```powershell
   cd C:\Users\hwkim\Desktop\Codyssey\A1-3
   python --version
   python dev_server.py
   ```

3. 브라우저에서 [로컬 RE:ST](http://localhost:3000)를 엽니다. 서버가 실행 중인 터미널은 그대로 둡니다.
4. Home → 시작 → About → Personal → 코스 선택 → 호흡 시작 순서로 사용합니다.
5. 종료는 서버 터미널에서 `Ctrl+C`입니다. 3000번 포트를 이미 사용 중이라면 `python dev_server.py --port 3001`로 실행하고 [3001번 로컬 주소](http://localhost:3001)를 엽니다.

Python 3.12 이상이 필요합니다. 별도 `pip install`이나 프론트엔드 빌드는 필요 없습니다. `index.html`을 더블 클릭하거나 일반 정적 서버만 쓰면 Python API가 실행되지 않으니 위 명령을 사용합니다.

## 2. Codyssey API 키 설정

이 프로젝트는 사용자가 제공한 Codyssey API 콘솔의 **OpenAI 호환 Chat Completions** 방식으로 연결합니다. OpenAI 본사에서 새 키를 발급할 필요가 없습니다.

1. Codyssey API 콘솔에서 발급한 키를 사용합니다. 기존 `.env`의 키를 그대로 사용해 실제 추천 성공을 확인했습니다.
2. `.env`의 `OPENAI_API_KEY=` 뒤에 Codyssey 키를 직접 저장합니다. 변수 이름은 호환성을 위해 유지했으며 키를 보내는 주소는 Codyssey입니다.
3. `OPENAI_MODEL=gpt-5-mini`로 설정합니다. 다른 모델을 쓰려면 Codyssey 콘솔에 나오는 사용 가능한 CHAT 모델 ID를 사용합니다.
4. 서버 터미널에서 `Ctrl+C`를 누른 뒤 `python dev_server.py`로 **실제로 재시작**합니다. 브라우저 새로고침만으로는 `.env` 변경이 반영되지 않습니다.
5. [로컬 Care](http://localhost:3000/#care)에서 추천을 요청합니다.

- API 주소: `https://copa.codyssey.kr/v1/chat/completions`
- 인증: 서버에서 `Authorization: Bearer`로 Codyssey 키 전달
- 요청: `model`, `messages`
- 응답: `choices[0].message.content`의 JSON을 서버에서 검증
- 키와 비밀번호는 대화·스크린샷·Git에 넣지 않습니다.

## 3. 실제 AI 추천 확인하기

1. [로컬 RE:ST Care](http://localhost:3000/#care)를 엽니다.
2. 환경: **집**, 현재 상황: **오랜 작업을 마치고 머리가 복잡해요.**, 필요한 도움: **긴장을 내려놓고 싶어요.**를 입력합니다.
3. **나에게 맞는 쉼 찾기**를 누릅니다. 로딩 후 코스명과 이유가 나타나는지 봅니다.
4. **이 코스로 쉬어가기**를 눌러 추천된 코스가 이미 선택돼 있는지 확인합니다.
5. 실패하면 개발자 도구 `F12` → Network → `recommend`의 상태를 먼저 확인합니다. 터미널에는 같은 요청의 오류 코드가 나옵니다. 입력과 키는 로그에 남기지 않습니다.
6. 성공한 입력 화면과 결과 화면을 `docs/evidence/`에 저장합니다. 파일명 예: `ai-input-real.png`, `ai-result-real.png`. 키를 편집하는 창은 캡처하지 않습니다.

추천 내용은 실행마다 달라질 수 있으므로 특정 코스가 반드시 나와야 하는 것은 아닙니다. ID가 `focus` / `sleep` / `relax` 중 하나인지, 이유가 입력과 관련 있는지 확인합니다. 현재 제공된 `TEST-ONLY` 스크린샷은 실제 AI 성공 증빙으로 제출하지 않습니다.

## 4. GitHub 로그인 복구하기

기존 저장소는 [Duebii/Codyssey](https://github.com/Duebii/Codyssey)입니다. `A1-3` 안에 새 Git 저장소를 만들 필요가 없습니다. 현재 작업 브랜치는 `codex/rest-mvp`입니다.

1. 터미널에서 다음을 실행합니다.

   ```powershell
   cd C:\Users\hwkim\Desktop\Codyssey
   gh auth login --hostname github.com --git-protocol https --web
   ```

2. 터미널 안내에 따라 브라우저에서 GitHub에 로그인하고 기기 인증을 완료합니다. 로그인 정보는 GitHub 공식 페이지에만 입력합니다. 단기 인증 코드도 공개하거나 대화에 공유하지 않습니다.
3. 연결 상태와 Git 인증 연결을 확인합니다.

   ```powershell
   gh auth status
   gh auth setup-git
   git branch --show-current
   git status --short
   ```

브라우저 기반 로그인 절차는 [GitHub CLI 공식 `gh auth login` 문서](https://cli.github.com/manual/gh_auth_login)에 안내돼 있습니다. 인증 실패가 계속되면 같은 공식 문서의 로그인 복구 절차를 확인합니다.

## 5. A1-3만 업로드하기

현재 다른 과제 폴더에도 기존 변경사항이 있습니다. **저장소 전체를 `git add .`로 추가하지 말고 `A1-3`만 지정합니다.**

1. 먼저 `.env`가 무시되는지와 A1-3 변경사항을 확인합니다.

   ```powershell
   git check-ignore A1-3/.env
   git status --short -- A1-3
   git log --oneline -5
   ```

2. 아직 커밋하지 않은 A1-3 변경사항이 있을 때만 다음을 실행합니다.

   ```powershell
   git add -- A1-3
   git diff --cached --name-only
   git diff --cached --stat
   git commit -m "feat: complete RE:ST MVP"
   ```

   목록이 `A1-3/` 파일로만 구성되어 있고 `.env`가 없음을 확인한 뒤 커밋합니다. 이미 로컬 커밋이 있고 새 변경이 없으면 이 단계를 건너뜁니다.

3. 현재 브랜치를 업로드합니다.

   ```powershell
   git push -u origin codex/rest-mvp
   ```

4. GitHub 저장소에서 `codex/rest-mvp` 브랜치를 선택해 `A1-3/index.html`, `api/recommend.py`, `audio/`가 올라왔는지 확인합니다.
5. GitHub의 **Compare & pull request**로 `main`을 대상으로 PR을 엽니다. 변경 파일이 의도한 A1-3 작업인지 검토한 뒤 병합합니다. 이 안내에서는 기본 운영 브랜치를 `main`으로 사용합니다. 다른 기존 과제의 미커밋 파일은 PR에 포함되지 않습니다.

## 6. Vercel 로그인과 프로젝트 연결

명령줄에 Vercel 비밀번호나 토큰을 넣을 필요가 없는 웹 대시보드 방식입니다.

1. [Vercel](https://vercel.com/)에서 **Log In → Continue with GitHub**를 선택합니다.
2. GitHub 공식 화면에서 연동을 승인합니다. 비밀번호·추가 인증은 해당 서비스 화면에서 직접 완료합니다.
3. Vercel 대시보드의 **Add New → Project**에서 `Duebii/Codyssey`를 Import합니다.
4. 저장소가 보이지 않으면 GitHub 연동의 저장소 접근 설정에서 `Codyssey`를 허용합니다.
5. 프로젝트 설정을 다음과 같이 지정합니다.

   | 설정 | 값 |
   | --- | --- |
   | Root Directory | **A1-3** |
   | Framework Preset | **Other** |
   | Production Branch | **main** (앞 단계 병합 후) |
   | Build Command | 비워 둠 / 추가 빌드 없음 |
   | Output Directory | 프로젝트 루트 `.` (`vercel.json`에 정의됨) |
   | Install Command | 기본값 유지; 프론트엔드 패키지 설치 없음 |

6. Root Directory에 `A1-3`를 지정해야 `/api/recommend`와 `/audio/...`가 올바른 위치에서 제공됩니다. 다른 과제 폴더를 배포 대상으로 선택하지 않습니다.

GitHub 연동의 자동 배포 동작은 [Vercel for GitHub 문서](https://vercel.com/docs/git/vercel-for-github)를 참고합니다. API는 미션의 `api/recommend.py` 구조에 맞춰 [Vercel의 파일 기반 Python Function 방식](https://vercel.com/docs/functions/runtimes/python/api-directory)으로 구현했습니다.

## 7. Vercel 환경 변수와 배포

1. Import 화면의 **Environment Variables**, 또는 프로젝트 **Settings → Environment Variables**에서 이름에 `OPENAI_API_KEY`를 입력합니다.
2. **Value에 실제 키를 직접 입력**합니다. 이 칸의 스크린샷은 공유하지 않습니다.
3. 적용 환경에서 **Production**을 선택합니다. 미리보기 배포에서도 AI를 쓸 계획이라면 **Preview**에도 설정합니다.
4. `OPENAI_MODEL`은 `gpt-5-mini`로 설정합니다. 생략해도 같은 모델을 사용합니다. `OPENAI_API_KEY` 값에는 Codyssey에서 발급한 키를 넣습니다.
5. **Deploy**를 누르고 Ready 상태가 될 때까지 기다립니다.
6. 배포 성공 화면에서 실제 공개 주소를 엽니다. 주소를 확인한 뒤 README의 배포 URL에 기록합니다.
7. 환경 변수를 나중에 추가·수정했다면 Deployments에서 **Redeploy**를 실행합니다. `.env`는 Vercel로 업로드되지 않으므로 로컬 키 설정과 Vercel 키 설정은 별개입니다.

환경 변수는 적용 환경과 배포 시점에 따라 달라집니다. [Vercel 환경 변수 공식 문서](https://vercel.com/docs/environment-variables)를 참고합니다.

## 8. 공개 URL에서 최종 확인

1. 로그아웃 또는 시크릿 창에서 공개 주소가 열리는지 확인합니다. Vercel 로그인 요구가 있다면 프로젝트의 Deployment Protection과 운영 도메인 설정을 확인합니다.
2. Home → About → Personal → 세 코스 각각 시작·일시정지·재개를 확인합니다.
3. 한 코스를 3분 끝까지 재생하여 완료 안내와 자동 정지를 확인합니다.
4. Care에서 빈 입력, 정상 입력의 실제 추천, 추천된 코스 선택을 확인합니다.
5. `F12`의 기기 보기에서 모바일 390×844, 데스크톱 1440×900을 확인합니다.
6. 실제 추천 화면과 공개 주소·Vercel Ready 화면의 증빙을 저장합니다. API 키는 포함하지 않습니다.
7. [증빙 안내](evidence/README.md)의 미완료 항목과 README의 배포 상태를 갱신합니다.

## 9. 이후 수정과 재배포

화면을 수정한 뒤 로컬에서 먼저 확인합니다. 해당 변경을 A1-3 범위로 커밋하고 작업 브랜치에 push → PR 검토·병합을 진행하면, GitHub와 연결된 Vercel이 운영 브랜치 변경을 받아 새 배포를 실행합니다. 코드 변경 없는 환경 변수 수정은 별도의 Redeploy가 필요합니다. 배포가 실패하면 Deployments의 Build Logs, API만 실패하면 Function Logs부터 확인합니다.
