# Product

<!-- impeccable:product-schema 1 -->

## Platform
web

## Stack
사용자 지정: HTML/CSS/JavaScript, 프레임워크 금지. FastAPI, Firestore, GPT. 백엔드 Render, 프론트 Vercel 배포는 10단계.

## Users
프리랜서·취업·창업에 관심이 많고 우선순위와 실행 방법을 필요할 때 상담받고 싶은 사용자 본인.

## Product Purpose
김실장은 기록을 참고해 우선순위와 실행 전략을 세우고, 반복 업무의 개선·자동화 방법을 설계한다. 사용자가 물어볼 때만 답한다.

## Operating Context
네 화면: 김실장 상담, 작업 기록, 기록 요약, 이전 상담. 목표·가용 시간·할 일·제약은 선택 입력한다. 이전 조건과 대화를 불러온다.

## Capabilities and Constraints
150건의 시연용 가상 작업 기록을 사용한다. 실제 개인 행동·마음·성격으로 해석하지 않는다. 기록 CRUD, 요약, 채팅 자동 저장, 대화 불러오기·삭제. 자동화는 설계만 한다. 키는 서버에만 보관한다. 이번 범위는 8단계 웹 UI 구현과 기능 확인이다.

## Brand Commitments
이름은 사용자가 정한 ‘김실장’. 쉬운 한국어, 부담을 줄이고 구체적인 다음 행동을 돕는 말투.

2026-10-27 사용자가 웹 화면을 “차분하고 세련된 — 정돈된 화면과 감각적인 색 포인트”로 다듬도록 선택했습니다. 구체적인 잉크 블루 색상·서체는 이 취향에 맞춘 구현자의 선택입니다.

## Evidence on Hand
상세 제품 계약: docs/PRODUCT_SPEC.md, docs/API_CONTRACT.md. 가상 데이터: data/work_records.json. 실제 Firestore 기록 150건, 6,524분. 기존 저장 상담은 시연용이다. 과장된 효과·후기·개인 정보는 만들지 않는다.

## Product Principles
- 사용자 요청으로 상담한다.
- 관찰과 추정, 가상 기록과 현재 조건을 구분한다.
- 우선순위마다 실행 방법·완료 기준·대안을 제시한다.
- 저장 실패에도 입력을 보존하고 유료 요청은 자동 반복하지 않는다.

## Accessibility & Inclusion
모바일, 키보드 조작, 명시적인 라벨·로딩·오류·빈 상태를 제공한다.
