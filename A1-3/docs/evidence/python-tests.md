# Python 검증 결과

실행 명령: `python -m unittest discover -s tests -p 'test_*.py' -v`

실제 실행 결과: **Ran 13 tests in 0.588s / OK**. 로컬 Python 3.12.0에서 실행했습니다. 외부 AI 네트워크 호출은 모의 전송으로 대체하여 API 비용·키 없이 검사했습니다.

검사한 항목:

1. 요청 본문 파싱·본문 크기·Content-Type 검증을 AI 호출 전에 수행.
2. 키 미설정 시 HTTP 503, 안전한 메시지, `no-store`, 요청 ID.
3. GET 거부, HTTP 405와 `Allow: POST`.
4. HTTP 200 응답에 `course_id`, `course`, `reason` 반환(모의 AI).
5. 예상 밖 예외의 민감한 상세 메시지가 사용자에게 노출되지 않음.
6. OpenAI 실제 요청 URL·Schema·모델·`store: false`·timeout 구성(모의 전송).
7. 세 ID의 한국어 코스명이 서버의 허용 목록과 일치.
8. 키가 없으면 외부 요청 함수를 호출하지 않음.
9. OpenAI timeout, 네트워크 오류, HTTP 401·429·500 매핑.
10. AI 거절·미완료·잘못된 JSON 처리.
11. 허용하지 않은 ID·자료형·빈 이유·긴 이유·추가 필드 거부.
12. 필수값 누락·공백·잘못된 자료형·길이 초과·제어문자 거부.
13. 정상 입력 공백 정리·사용하지 않는 필드 제외.

실제 OpenAI 서비스에서 추천이 성공했다는 뜻은 아닙니다. 실제 성공 테스트는 API 키 설정 후 별도로 진행해야 합니다.
