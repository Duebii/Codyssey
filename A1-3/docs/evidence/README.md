# 증빙 자료와 확인 범위

## Computer Use 직접 캡처 (2026-09-10)

Chrome의 실제 로컬 서비스에서 Computer Use로 입력·버튼 클릭·추천 코스 이동을 수행하고, 표시된 화면을 원본 JPEG로 저장했습니다. 모의 응답이나 화면 합성은 사용하지 않았습니다.

- [3번: AI 입력](03-ai-input-computer-use.jpg)
- [3번: 실제 요청 중 로딩](03-ai-loading-computer-use.jpg)
- [3번: 실제 AI 추천 결과](03-ai-result-computer-use.jpg)
- [3번: 추천된 코스 자동 선택](03-ai-course-selected-computer-use.jpg)

검증 입력은 `집 / 오랜 작업을 마치고 잠깐 쉬고 싶어요. / 긴장을 내려놓고 싶어요.`이며, 실제 결과는 `긴장을 푸는 호흡`입니다. API 키는 화면에 포함되지 않았습니다. 공개 배포가 아닌 로컬 실행 증빙입니다.

## Codyssey 실제 AI 연동 검증 (2026-09-10)

기존 키를 그대로 사용하고 연결 주소를 `https://copa.codyssey.kr/v1/chat/completions`, 모델을 `gpt-5-mini`로 변경했습니다. 실제 요청 HTTP 200, 추천 이유 표시, 추천된 코스의 자동 선택을 브라우저에서 확인했습니다.

- [실제 AI 입력 화면](ai-input-real.png)
- [실제 AI 추천 결과](ai-result-real.png)
- [실제 호출 검증 기록](codyssey-live-report.json): `actualAI: true`, 키 미포함, 검증용 일반 문장만 사용.

아래 `browser-report.json`과 `TEST-ONLY` 이미지는 최초 구현 당시의 모의 응답 검사 기록이며 위 실제 호출 기록과 구분합니다. Codyssey 요청·응답 형식으로 변경한 서버 테스트도 13개 모두 통과했습니다.

## 실제 로컬 서비스 화면

- 데스크톱: [Home](desktop-home.png), [About](desktop-about.png), [Relax](desktop-relax.png), [Care](desktop-care.png), [호흡](desktop-breathe.png)
- 모바일: [Home](mobile-home.png), [About](mobile-about.png), [Relax](mobile-relax.png), [Care](mobile-care.png), [호흡](mobile-breathe.png)
- 태블릿: `tablet-home.png`, `tablet-about.png`, `tablet-relax.png`, `tablet-care.png`, `tablet-breathe.png`
- 실제 입력: [모바일 Care 입력](mobile-care-input.png)
- 실제 로컬 API 키 미설정 상태: [연결 안내](mobile-api-not-configured.png)
- 실제 180초 재생 완료: [완료 안내](desktop-completion-real-180s.png)

화면 크기는 데스크톱 1440×900, 모바일 390×844, 태블릿 768×1024입니다. 긴 화면은 해당 너비의 전체 페이지로 캡처했으므로 이미지 높이가 뷰포트보다 클 수 있습니다. 320×740도 자동 테스트에서 가로 넘침을 확인했습니다.

## 테스트 전용 이미지 — 실제 AI 증빙 아님

[mobile-result-TEST-ONLY.png](mobile-result-TEST-ONLY.png)는 Playwright가 주입한 모의 응답으로 결과 화면과 코스 이동을 확인한 자료입니다. **화면의 이유에도 ‘테스트용 모의 응답입니다. 실제 AI 추천이 아닙니다.’라고 표시했습니다.** 실제 AI 성공 증빙으로 제출하지 않습니다. 서비스 코드에는 이 임시 추천 기능이 없습니다.

## 검증 기록

- `browser-report.json`: 실제 MP3 세 개 재생·일시정지·재개, 실제 180초 세션, 폼·레이아웃 검사 결과. `actualAI: false`를 명시했습니다.
- `browser-smoke-report.json`: 최종 화면 수정 이후의 짧은 재검증 결과(3분 대기 제외).
- `additional-checks.json`: 키보드 메뉴·코스 선택, 애니메이션 감소, Vercel 보안 헤더 적용, 비공개 파일 차단, 추천 요청 취소, 사운드 오류 후 재시도 검사. `tests/browser-edge-check.cjs`로 재실행할 수 있습니다.
- [Python 테스트 결과](python-tests.md): 서버 테스트 13개 통과.
- `asset-integrity.json`: 원본과 복사된 세 음원의 SHA-256 일치 기록.
- [AI 코딩 도구 사용 과정](development-log.md): 이 대화의 실제 발췌와 작업·검증 요약.

## 아직 준비하지 않은 제출 증빙

- **공개 URL·Vercel 배포:** 사용자 요청으로 계정 설정·배포를 나중에 진행하므로 없음.
- **GitHub 원격 커밋 화면:** GitHub 인증 후 push·확인 필요.

이 항목들은 구현 완료로 표기하지 않았습니다. [계정 설정·배포 안내](../setup-and-deploy.md)의 순서대로 진행한 뒤 실제 결과만 추가합니다. 키·비밀번호·비밀 환경 변수의 값은 캡처하지 않습니다.
