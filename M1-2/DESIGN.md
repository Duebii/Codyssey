---
name: "김실장"
description: "작업 기록을 읽고 다음 행동을 정하는 차분한 업무 상담 화면"
colors:
  primary: "#234e70"
  data: "#2d6b97"
  negative: "#a13543"
  ground: "#edf3f8"
  surface: "#fff"
  raised: "#f3f7fb"
  active: "#fff"
  text: "#233b50"
  muted: "#5b7082"
  border: "#dce5ed"
  rule: "#eaf0f5"
  control: "#7d8d9d"
  primary-hover: "#183c5a"
  secondary-border: "#bcccd9"
  secondary-border-hover: "#2d6b97"
  nav-text: "#5b7082"
  nav-hover: "#e3edf5"
  disabled-ground: "#e5ecf2"
  disabled-text: "#526b80"
  disabled-border: "#dce5ed"
  placeholder: "#607487"
  context-ground: "#f0f6fb"
  budget-ground: "#f0f6fb"
  feedback-text: "#5b7082"
  error-ground: "#fff1f2"
  error-text: "#923244"
  delete-text: "#a13543"
  toast-ground: "#233f57"
  bar-track: "#edf3f8"
  toolbar-ground: "#fafcfe"
  editor-ground: "#f8fafc"
  selection-ground: "#dceaf5"
  scrollbar: "#bdcbd7"
  starter-hover-border: "#8da7bc"
typography:
  headline:
    fontFamily: '"IBM Plex Sans", "IBM Plex Sans KR", sans-serif'
    fontSize: "28px"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "-.025em"
  welcome:
    fontFamily: '"IBM Plex Sans", "IBM Plex Sans KR", sans-serif'
    fontSize: "30px"
    fontWeight: 500
    lineHeight: 1.45
    letterSpacing: "-.035em"
  title:
    fontFamily: '"IBM Plex Sans", "IBM Plex Sans KR", sans-serif'
    fontSize: "16px"
    fontWeight: 500
    lineHeight: 1.55
    letterSpacing: "-.025em"
  body:
    fontFamily: '"IBM Plex Sans", "IBM Plex Sans KR", sans-serif'
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: '"IBM Plex Sans", "IBM Plex Sans KR", sans-serif'
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.65
  caption:
    fontFamily: '"IBM Plex Sans", "IBM Plex Sans KR", sans-serif'
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.65
  metric:
    fontFamily: '"IBM Plex Sans", "IBM Plex Sans KR", sans-serif'
    fontSize: "32px"
    fontWeight: 400
    lineHeight: 1.3
    letterSpacing: "-.025em"
rounded:
  tag: "4px"
  subtle: "6px"
  control: "8px"
  selection: "10px"
  composer: "12px"
  panel: "14px"
  sheet: "16px"
  dialog: "16px"
spacing:
  xxs: "4px"
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  sheet-gutter: "32px"
  gap: "24px"
  roomy: "28px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "9px 16px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.surface}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "9px 16px"
  button-danger:
    backgroundColor: "{colors.negative}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "9px 16px"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    padding: "4px 0"
  button-icon:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.subtle}"
    padding: "4px 0"
  field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "10px 11px"
  navigation-item:
    textColor: "{colors.nav-text}"
    rounded: "{rounded.selection}"
    padding: "11px 14px"
  navigation-item-current:
    backgroundColor: "{colors.active}"
    textColor: "{colors.primary}"
  demo-tag:
    textColor: "{colors.muted}"
    rounded: "{rounded.tag}"
    padding: "2px 7px"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.panel}"
    padding: "24px"
  plan-budget:
    backgroundColor: "{colors.budget-ground}"
    textColor: "{colors.text}"
    rounded: "{rounded.subtle}"
    padding: "12px 14px"
  feedback:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.feedback-text}"
    rounded: "{rounded.subtle}"
    padding: "12px 14px"
  feedback-error:
    backgroundColor: "{colors.error-ground}"
    textColor: "{colors.error-text}"
    rounded: "{rounded.subtle}"
    padding: "12px 14px"
---

# Design System: 김실장

## Overview

**Creative North Star: "Ink-blue framed sheet"**

은은한 푸른 회색 틀 안에 흰 작업 면을 놓습니다. 잉크 블루의 주요 행동과 제목, 옅은 파랑의 참고 면, 분명한 입력 경계로 상담과 기록을 읽고 조작하는 순서를 드러냅니다. 쉬운 한국어와 구체적인 다음 행동을 돕는 말투는 제품의 지속적인 약속입니다.

이 문서는 `frontend/styles.css`, `frontend/index.html`, `frontend/app.js`, `frontend/lib.js`, `frontend/mark.svg`의 현재 구현을 기록합니다. 사용자는 2026-10-27에 “차분하고 세련된 — 정돈된 화면과 감각적인 색 포인트”를 선택했습니다. Framed sheet와 seed `2102444201`, 구체적인 잉크 블루 색상과 IBM Plex 서체는 그 취향에 맞춘 구현자의 선택입니다. 승인된 이미지 시안이나 별도 브랜드 자료는 없습니다. 화면별 구성의 근거는 `docs/UI_DESIGN.md`를 따릅니다.

**Key Characteristics:**

- 푸른 회색 틀, 흰 작업 면, 가는 경계선.
- IBM Plex 서체와 여유를 둔 제목, 정렬된 본문·수치.
- 주요 행동·선택·데이터·포커스의 파랑, 오류와 삭제의 붉은색.
- 그림자 없는 작업 면과 상태를 설명하는 짧은 한국어.

## Colors

앞부분의 색 토큰이 기준입니다. 본문에서는 색의 역할만 설명합니다.

### Primary

- **잉크 블루** (`primary`): 질문 전송과 저장 같은 주요 버튼, 현재 메뉴의 글자와 요약 수치. 주요 버튼 호버는 `primary-hover`입니다.
- **기록 파랑** (`data`): 분야별 시간 막대와 키보드 포커스.
- **삭제 적색** (`negative`): 삭제 확인의 실행 버튼. 텍스트 삭제 동작은 `delete-text`를 사용합니다.

### Neutral

- **작업 바탕 / 종이 면** (`ground`, `surface`): 페이지와 읽기·편집 패널.
- **부드러운 강조 면 / 흰 선택 면** (`raised`, `active`): 사용자 메시지는 옅은 파랑, 현재 메뉴는 푸른 틀 위의 흰 면입니다.
- **본문 / 보조 글자** (`text`, `muted`): 읽을 내용과 라벨·시간·설명.
- **패널 경계 / 내부 구분 / 입력 경계** (`border`, `rule`, `control`): 컨테이너, 반복 행, 조작 가능한 필드를 구별합니다.
- **참고 / 조건 / 시간 예산 면** (`context-ground`, `budget-ground`): 상담 참고 첫 구획, 접이식 입력 영역과 실행 계획의 시간 합계.
- **도구 / 편집 면** (`toolbar-ground`, `editor-ground`): 상담 도구줄과 기록 편집기를 흰 목록에서 부드럽게 구별합니다.
- **선택 / 스크롤 / 시작 질문 경계** (`selection-ground`, `scrollbar`, `starter-hover-border`): 텍스트 선택, 가는 스크롤 막대, 시작 질문 호버의 현재 색입니다.
- **상태 면** (`error-ground`, `error-text`, `feedback-text`, `toast-ground`): 오류, 인라인 진행·완료, 임시 알림.
- 나머지 상태 토큰은 버튼·메뉴·플레이스홀더의 현재 CSS 값을 보존합니다. 색상 단계나 테마 전환은 구현되어 있지 않습니다.

**The Functional Color Rule.** 파랑은 주요 행동, 현재 메뉴, 데이터와 포커스에 사용합니다. 시간의 증가·감소를 좋고 나쁨의 색으로 분류하지 않습니다.

## Typography

**Body Font:** IBM Plex Sans → IBM Plex Sans KR → sans-serif. 두 서체의 굵기 (400, 500, 600)를 Google Fonts에서 불러옵니다. 별도 디스플레이·고정폭 서체는 없습니다.

### Hierarchy

- **Headline:** 화면 제목. (480px 이하)에서는 (23px)로 줄고 한국어 단어를 가급적 유지합니다.
- **Welcome:** 상담 첫 화면의 문장. (1000px 이하)에서 (27px), (700px 이하)에서 (25px), (480px 이하)에서 행간 (1.5)입니다. 환영 구획의 최대 폭은 (510px)입니다.
- **Title:** 패널 제목. 하위 제목은 (15px, 500)이며 참고 영역 제목은 (13px, 500)입니다.
- **Body / Label / Caption:** 본문, 폼 라벨, 시간·설명 순서입니다. 날짜·수치·숫자 입력·페이지 탐색은 `tabular-nums`를 사용합니다.
- **Metric:** 요약 수치. (700px 이하)에서 (27px), (480px 이하)에서 (26px)입니다. 단위는 (13px) 보조 글자입니다.
- 대화 본문은 행간 (1.9), 최대 폭 (76ch)입니다. 긴 입력과 서버 문장은 줄바꿈할 수 있으며 원래 줄바꿈을 보존합니다.
- 상담 참고의 대표 수치는 (34px, 400, 행간 1.2, 자간 -.035em), (480px 이하)에서는 (26px)입니다.
- 로고 옆 제품명은 (23px, 600, 행간 1.3, 자간 -.04em), (1000px 이하)에서는 (20px)입니다. 작은 근거·시각·푸터에는 (11px)도 사용합니다.

**The Numeric Alignment Rule.** 비교하는 수치는 일정한 숫자 폭을 유지하고, 데스크톱 표의 시간 값은 오른쪽으로 정렬합니다. 없는 측정값은 `—`로 표시합니다.

## Layout

- 데스크톱은 고정 왼쪽 메뉴 (224px), 흰 작업 면의 바깥 여백 (위·오른쪽·아래 16px, 왼쪽 232px), 면 안쪽 여백 (위 26px, 좌우 32px)입니다. 본문은 남은 폭을 사용하고, (1700px 이상)에서는 안쪽 좌우 여백이 (44px)입니다.
- 상담은 유동 본문과 참고 열 (268px), 기록은 목록과 편집 열 (286px), 요약은 (1.25fr : 1fr)입니다. 주요 열 간격과 패널 안쪽 여백은 (24px)입니다. 이전 상담 패널은 최대 폭 (1060px)입니다.
- (1200px 이하): 메뉴 (200px), 본문 왼쪽 바깥 여백 (208px), 안쪽 좌우 여백 (24px), 상담 참고 열 (240px). 기록 편집기를 목록 아래로 이동하고 최대 폭을 (600px)로 둡니다.
- (1000px 이하): 메뉴를 페이지 위의 가로 탐색으로 바꿉니다. 작업 면 바깥 여백은 (위 0, 좌우·아래 12px), 안쪽 여백은 (위·좌우 24px)입니다. 상담 참고 열은 (230px), 열 간격은 (20px)입니다.
- (700px 이하): 네 탐색 항목을 같은 폭의 한 줄에 아이콘 위·글자 아래로 배치합니다. 작업 면 바깥 여백을 없애고 윗모서리와 윗경계만 남기며 안쪽 여백은 (위 22px, 좌우 20px)입니다. 상담·요약은 한 열, 요약 지표와 참고 영역은 두 열입니다. 참고 도움말은 숨기고 반복 작업 표는 라벨이 붙은 행, 주별 목록은 한 열로 바꿉니다.
- (480px 이하): 본문 여백 (위 19px, 좌우 16px), 패널 여백 (18px). 네 칸 탐색을 유지합니다. 참고 영역은 한 열이며 최근 상담 부분을 숨깁니다. 현재 상황 입력은 한 열, 기록 표는 날짜·작업명·시간 라벨이 붙은 행으로 바꿉니다. 기록 편집기의 시간 입력 두 열은 유지합니다.
- 상담 메시지 영역 높이는 `clamp(344px, calc(100dvh - 500px), 620px)`, (480px 이하)에서는 (380px)입니다. 다만 (700px 이하)의 환영 화면은 자동 높이와 보이는 넘침을 사용해 시작 질문을 펼칩니다. 대화가 있으면 메시지 영역이 세로 스크롤하며 조건 입력 영역은 최대 (55vh)입니다.
- 반복 간격은 앞부분의 spacing을 사용합니다. 폼 열 간격 (12px), 반복 메시지 구분 후 여백 (24px), 페이지 제목 아래 (28px) 등은 현재 화면의 구체적인 배치 값입니다.

## Elevation & Depth

작업 패널과 메시지에는 그림자를 쓰지 않습니다. 푸른 틀·흰 면·연한 강조 면과 가는 경계선으로 계층을 구별합니다. 임시 알림에만 그림자 (`0 6px 22px #0002`)가 있습니다. 삭제 확인창의 뒤는 반투명 잉크색 가림막 (`#233b5066`)으로 덮습니다.

**The Flat Surface Rule.** 지속되는 작업 면은 평평하게 유지합니다. 임시 알림의 그림자를 패널 스타일로 확장하지 않습니다.

## Shapes

역할에 맞춰 곡률을 조금씩 넓힙니다. 태그, 아이콘·시간 예산·피드백·알림, 버튼·필드·시작 질문, 탐색·사용자 메시지, 질문 입력기, 패널, 작업 면·확인창의 모서리는 각각 rounded 토큰을 따릅니다. 패널과 필드는 (1px) 선이며, 작은 선 아이콘은 (18×18px, 선 두께 1.6, 둥근 끝과 연결)입니다.

자체 SVG 표식은 옅은 푸른 문서 면 위에 잉크색 모서리와 파란 체크를 결합합니다. 상담 시작 부분과 제품명 옆에서 사용하며, (700px 이하)의 상담 시작 부분에서는 숨깁니다. 장식 사진이나 삽화는 현재 구현에 없습니다.

## Components

### Buttons

- 주요·보조·삭제 버튼은 최소 높이 (40px), 행간 (1.4), 아이콘 간격 (9px)입니다. (480px 이하)에서는 최소 높이 (44px), 안쪽 여백 (10px 12px)입니다.
- 주요 버튼은 잉크 블루 면, 보조 버튼은 흰 면과 `secondary-border`, 삭제 확인은 적색 면입니다. 주요 호버는 더 짙은 잉크색, 보조 호버는 파란 경계입니다. 삭제 버튼에는 별도 호버 색이 없습니다.
- 텍스트 동작은 호버 시 밑줄, 아이콘 동작은 연한 면을 사용합니다. 아이콘 버튼은 기본 (36×36px), 모바일 (44×44px) 이상입니다.
- 비활성 동작은 네이티브 `disabled`와 금지 커서를 사용합니다. 주요·보조·삭제 변형도 비활성 면·글자·경계 색으로 바뀝니다.
- 시작 질문은 내용에 맞는 짧은 버튼을 감싸서 배치합니다. 호버는 옅은 파란 면과 강조 경계이며, 모바일 최소 높이는 (44px)입니다.

### Inputs / Fields

- 명시적인 라벨, 흰 면, 입력 경계 토큰, 최소 높이 (42px)입니다. (480px 이하)에서는 (44px)입니다. 질문 입력기는 별도의 composer 모서리와 포커스 시 잉크색 경계를 쓰며 내부 텍스트 영역에는 테두리가 없습니다. 도구줄 선택 필드는 기본 (32px), 모바일 (44px)입니다.
- 모든 키보드 포커스는 파란 외곽선 (2px, 바깥 간격 3px)입니다. 질문 텍스트 영역은 선을 안쪽에 배치합니다 (offset -3px). 플레이스홀더는 라벨을 대체하지 않습니다.
- 질문 입력 아래에 전송 버튼, 위에 현재 상황 접이식 입력이 있습니다. 전송 중 질문·조건·종류·상담 전환 동작을 잠그며 `aria-busy`를 설정합니다.

### Navigation / Tag

- 현재 메뉴는 흰 면·잉크색 글자·중간 굵기로 표시하고 `aria-current="page"`를 제공합니다. 데스크톱에는 오른쪽의 작은 파란 점 (4px)이 있으며 (1000px 이하)에서는 숨깁니다. 기본 최소 높이는 (46px), (700px 이하) 네 칸 메뉴는 (58px)입니다. 호버의 면·글자는 (160ms, ease-out)로 바뀝니다. 화면 전환 시 제목으로 키보드 초점을 이동합니다.
- 시연 태그는 왼쪽 메뉴에서만 가는 테두리와 작은 모서리를 가진 표식입니다. 상단의 같은 안내는 테두리 없는 글자입니다. 필터 칩은 구현되어 있지 않습니다.

### Cards / Containers

- 패널은 흰 면과 연한 경계를 사용합니다. 행·표·대화는 별도 그림자 카드 대신 내부 구분선으로 나눕니다.
- 기록 편집기는 옅은 편집 면을 사용합니다. 작업 메모는 “메모 보기” 네이티브 펼치기에 담고 원래 줄바꿈을 보존합니다. 긴 내용은 줄바꿈하며 (480px 이하) 펼치기 조작은 최소 높이 (44px)입니다.
- 사용자 메시지는 연한 면으로 묶고 답변은 문서처럼 펼칩니다. 실행 계획은 시간 예산 면, 우선순위, 완료 기준·단계·첫 행동, 접이식 점검·대안으로 구성됩니다. (480px 이하)에서 시간 예산의 수치가 다음 줄로 내려갑니다.

### States / Dialog

- 읽는 중에는 상태 문장과 회전 표시 (1초, linear)를 사용합니다. (12초) 후에는 기다림을 설명하는 문장으로 바뀝니다. 빈 목록은 이유와 다음 동작, 실패는 설명과 명시적 재시도 동작을 제공합니다.
- 실패한 질문·기록 입력을 보존합니다. 충돌 후 최신 대화를 불러와도 작성한 질문, 변경한 조건, 선택한 상담 종류를 유지합니다. 요청을 자동 재전송하지 않습니다.
- 인라인 오류는 연한 적색 면과 오류 글자, `role="alert"`로 구별합니다. 기록 저장 상태는 `role="status"`입니다. 상담 완료는 전역의 시각적으로 숨긴 `polite` 안내로 전달합니다.
- 임시 알림은 화면 아래 (24px)에 나타나고 (6.5초) 뒤 숨습니다. 데스크톱에서는 작업 영역 중심, 상단 탐색으로 바뀐 화면에서는 뷰포트 중심에 놓입니다.
- 삭제는 네이티브 대화상자로 대상과 범위를 설명합니다. 확인창은 최대 폭 (440px), 화면보다 (32px) 좁고 안쪽 여백은 (28px)입니다. 첫 초점은 취소이며 처리 중 두 동작을 잠급니다.
- 동작 감소 설정에서는 부드러운 스크롤을 끄고, 회전은 매우 짧은 한 번으로 줄이며 메뉴 전환 효과를 없앱니다. 장식 애니메이션은 없습니다.

## Do's and Don'ts

### Conversation workspace · 2026-10-28

첫 질문 전의 두 열 안내 화면을 유지합니다. 전송 후에는 흰 작업 면 전체를 대화에 사용하고 참고 열을 버튼으로 접습니다. 대화 본문은 16px / 1.9, 제목은 데스크톱 23px·모바일 20px, 역할·시간·상태는 기존 보조 크기를 사용합니다. 입력칸은 대화 아래에 두며 현재 상황은 펼치기로 접근합니다. 새 답변은 시작 부분부터 읽고 새 상담은 안내 화면으로 돌아갑니다.

브라우저에 보관한 초안과 Firestore에 저장된 상담을 구별합니다. 저장 목적지는 ‘이전 상담’으로 명시합니다. 상담 복원 중 조회 실패 시 질문을 유지하고 전송을 막아 엉뚱한 새 상담이 생기지 않도록 합니다. 첫 화면과 채팅 화면 모두 임시 보관 가능 여부를 글로 표시합니다.

### Do:

- **Do** 입력 경계와 내부 구분선의 역할을 구별하고 모든 키보드 포커스를 보이게 합니다.
- **Do** 긴 한국어, 수치 단위, 모바일 행 라벨이 읽히도록 줄바꿈과 숫자 정렬을 유지합니다.
- **Do** 로딩·빈 상태·실패·저장 완료를 문장과 조작 상태로 구분하고 실패한 입력을 남깁니다.
- **Do** 새 화면에도 현재의 IBM Plex 서체 스택, 역할별 모서리, 푸른 틀과 평평한 작업 면의 간격 위계를 적용합니다.

### Don't:

- **Don't** 시간 증감에 성과의 좋고 나쁨을 나타내는 색을 추가하지 않습니다.
- **Don't** 패널에 임시 알림의 그림자를 재사용하지 않습니다.
- **Don't** 없는 값을 임의의 수치로 채우거나 플레이스홀더만으로 입력 목적을 전달하지 않습니다.
- **Don't** 구현자가 선택한 스타일을 사용자가 확정한 브랜드 취향으로 기록하지 않습니다.
