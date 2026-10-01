# M1-1 달러·유로·엔화의 원화 기준 환율 분석

분석 기간: 2020-01-01~2026-08-31.

현재 단계: 데이터 수집·정제·분석과 리포트·회고 작성 완료. GitHub 제출 파일을 최종 확인하고 있다.

먼저 [분석 리포트](outputs/REPORT.md)를 읽는다. 그래프 3개, 인사이트 3개, 처리 기준, 한계, AI 사용 로그를 포함한다.

진행 상황은 [작업 체크리스트](outputs/WORKLIST.md)에 기록하고 단계 완료 시 갱신한다.

## 제출 안내

- [GitHub 프로젝트 폴더](https://github.com/Duebii/Codyssey/tree/main/M1-1)
- [GitHub 분석 리포트](https://github.com/Duebii/Codyssey/blob/main/M1-1/outputs/REPORT.md)
- [필수 요구사항 대조와 설명 연습](outputs/SUBMISSION.md)

코드·원본 데이터·리포트·그래프·의존성 목록을 이 폴더에 함께 포함한다. 대시보드와 분해·예측은 선택 과제이며 이번 제출에는 포함하지 않는다.

## 실행

Python 3.11 이상. 실제 검증 환경은 Python 3.12.14, numpy 2.3.5, pandas 3.0.1, matplotlib 3.11.2였다. 프로젝트 폴더에서 다음 순서로 실행한다.

```console
python -m pip install -r requirements.txt
python check_data.py
python analysis.py
python verify_analysis.py
```

원본 CSV 세 개와 수집 기록을 포함하므로 의존성 설치 후에는 점검·분석·검산을 인터넷 없이 실행할 수 있다. 최초 라이브러리 설치에는 인터넷이 필요하다.

원본을 새로 수집할 때만 `python collect_data.py`를 실행한다. 원본을 수동으로 받았다면 `python collect_data.py --local`로 수집 기록을 생성한다. 수집 스크립트는 표준 라이브러리만 사용한다.

- 원본: data/raw/DEXKOUS.csv, DEXUSEU.csv, DEXJPUS.csv
- 원본 수집 기록: data/raw/collection_metadata.json
- 분석용 데이터: outputs/fx_krw_clean.csv
- 점검·정제 설명: [outputs/DATA_CHECK.md](outputs/DATA_CHECK.md)
- 분석 수치·그래프 설명: [outputs/ANALYSIS_NOTES.md](outputs/ANALYSIS_NOTES.md)
- 그래프 3개: outputs/images/
- 검증 결과: [outputs/verification.json](outputs/verification.json)

독립 검산 코드는 pandas·numpy를 사용하지 않고 원본을 다시 읽어 Decimal과 statistics.stdev로 계산값을 대조한다. 원본 환산, 비교 지수, 변화율, 이동평균, 80개 월 구간의 표준편차, 리포트 링크를 확인했다. PNG의 한글·축·범례는 이미지로 확인했다.

그래프의 한글 표시에는 맑은 고딕(Windows), Noto Sans CJK KR, 나눔고딕 또는 AppleGothic이 필요하다. 코드가 설치된 글꼴을 확인한다.

## 분석 질문

1. 전체 기간에 세 통화의 원화 가격은 각각 얼마나 변했는가?
2. 세 통화의 상승·하락 흐름은 어느 구간에서 비슷하거나 달랐는가?
3. 어느 통화가 어느 시기에 가장 크게 흔들렸는가?

출처·관측 기준·단위·이용 조건 및 AI 사용 로그는 데이터 점검 문서에 기록했다.
