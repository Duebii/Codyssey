# 제공 자산과 사용 위치

모든 사진·음원은 사용자가 `A1-3`에 제공한 파일입니다. 원본 12개를 삭제·이동·수정하지 않았습니다. 이미지 생성 API나 외부 이미지 사이트를 사용하지 않았습니다.

## 실제 화면에 사용

| 원본 파일 | 원본 크기 | 용도 |
| --- | --- | --- |
| `01_home_ui_website_landing.png` | 1024×1536 | Home의 나무 문·햇살·의자 배경 |
| `02_About_Final.png` | 979×1607 | About의 소파·그림자 배경 |
| `Relax_2.jpeg` | 735×1133 | Relax의 휴식 사진 |
| `Relax.jpg` | 736×977 | Care의 손·패브릭 사진 |
| `focus.mp3` | 10,753,253 bytes / 약 336.04초 | `audio/focus.mp3`에 복사 |
| `sleep.mp3` | 6,551,808 bytes / 약 204.74초 | `audio/sleep.mp3`에 복사 |
| `relax.mp3` | 2,017,071 bytes / 약 63.03초 | `audio/relax.mp3`에 복사 |

Home은 SVG `viewBox="425 150 460 1386"`, About은 `viewBox="0 950 979 657"`로 글자가 없는 배경 영역만 보여줍니다. 원본 파일 자체를 잘라 저장한 것이 아니라 브라우저의 표시 영역을 지정한 것입니다. 모바일의 배경 영역과 사진 위치는 CSS로 조절합니다.

음원 길이는 실제 Chrome의 오디오 메타데이터에서 확인했습니다. 모든 코스의 사용 시간은 180초로 제한합니다. 63초 음원이 반복되는 실제 3분 세션도 검증했습니다. 원본과 `audio/` 복사본의 SHA-256 일치는 `asset-integrity.json`에 기록했습니다.

## 디자인 참고로 보존

`03_course.png`, `04_1_relax_ui_mockup.png`, `04_2_relax_ui_mockup.png`, `04_3_relax_ui_mockup.png`, `relax_ui_mockup.png`는 선택 화면·코스·호흡 원의 분위기와 구성을 참고했습니다. 새 HTML에는 기존 이미지의 글씨나 버튼을 클릭 UI로 사용하지 않습니다. 이번 MVP 범위에서 제외한 Archive와 로그인은 추가하지 않았습니다.

`images/favicon.svg`와 화면의 선형 아이콘은 CSS·HTML과 함께 작성한 코드 자산입니다. 폰트는 기기의 Georgia / 바탕 / 맑은 고딕 등 기본 글꼴을 사용하므로 외부 폰트 다운로드가 필요 없습니다.
