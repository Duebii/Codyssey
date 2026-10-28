"""Generate Kim Manager's reproducible, explicitly synthetic work-log fixtures.

Standard library only. This is a dataset utility, not application/backend code.
Usage: python scripts/generate_dummy_data.py [--check]
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
START = date(2026, 8, 26)
END = date(2026, 10, 20)
RANDOM_SEED = 1021


def make_records() -> list[dict]:
    """40 weekdays x 3 sessions + a fourth session on 30 weekdays = 150."""
    rng = random.Random(RANDOM_SEED)
    records: list[dict] = []
    weekdays = [
        START + timedelta(days=offset)
        for offset in range(56)
        if (START + timedelta(days=offset)).weekday() < 5
    ]

    def add(day: date, name: str, category: str, estimate: int, actual: int, memo: str) -> None:
        records.append(
            {
                "id": f"demo-{len(records) + 1:03d}",
                "date": day.isoformat(),
                "value": actual,
                "memo": memo,
                "task_name": name,
                "category": category,
                "estimated_minutes": estimate,
                "source": "synthetic",
            }
        )

    for index, day in enumerate(weekdays):
        week = (day - START).days // 7
        add(
            day, "자료 취합", "프리랜서", 20,
            20 + week * 4 + rng.randint(-2, 2),
            "시연용: 이메일과 공유 폴더에서 자료를 찾아 스프레드시트에 수동으로 옮김. "
            "누락 확인은 사람이 수행하며, 주차가 지날수록 취합할 자료가 늘어나는 가상 설정.",
        )
        if index % 2 == 0:
            add(
                day, "제안서 작성", "프리랜서", 40,
                65 + rng.randint(-5, 12),
                "시연용: 고객 요청을 읽고 범위·일정·견적을 문서로 작성. "
                "맞춤 문구와 견적 판단은 사람이 맡고, 예상보다 시간이 더 드는 가상 설정.",
            )
        else:
            add(
                day, "채용 공고 조사", "취업", 30,
                30 + week + rng.randint(-4, 6),
                "시연용: 채용 사이트에서 직무와 마감일을 확인해 후보 목록에 수동 입력. "
                "지원 적합성은 직접 판단하며 외부 사이트 자동 수집 허용 여부는 미확인.",
            )

        rotation = index % 4
        if rotation == 0:
            add(day, "포트폴리오 수정", "취업", 60, 60 + rng.randint(-8, 18),
                "시연용: 프로젝트 설명과 결과 이미지를 정리. 제출용 문구 초안까지를 이번 작업 범위로 설정.")
        elif rotation == 1:
            add(day, "고객 커뮤니케이션", "프리랜서", 20, 20 + rng.randint(-5, 10),
                "시연용: 진행 상황과 확인할 질문을 정리하고 답변 초안을 작성. 실제 발송은 수행하지 않은 가상 기록.")
        elif rotation == 2:
            add(day, "시장 조사", "창업", 45, 45 + rng.randint(-5, 15),
                "시연용: 경쟁 서비스의 공개 정보와 가격을 비교표에 정리. 비교 기준과 해석은 직접 판단.")
        else:
            add(day, "아이디어 정리", "창업", 30, 30 + rng.randint(-5, 10),
                "시연용: 해결할 문제와 가설, 다음 검증 행동을 한 페이지로 정리. 사업성 검증 결과는 아님.")

        if index % 4 != 3:
            if week < 4:
                add(day, "아이디어 검증 준비", "창업", 35, 35 + rng.randint(-4, 10),
                    "시연용: 인터뷰 질문과 검증할 가설을 작성. 인터뷰 진행이나 성과가 발생한 기록은 아님.")
            else:
                add(day, "지원서 작성", "취업", 50, 50 + rng.randint(-5, 15),
                    "시연용: 공고 요구 역량과 경험을 연결해 지원서 초안을 작성. "
                    "후반 4주에 취업 준비 비중을 높이는 가상 설정이며 실제 제출 결과는 없음.")

    return records


def make_summary(records: list[dict]) -> dict:
    """Analyze recorded sessions; missing dates are never converted to zero."""
    ordered = sorted(records, key=lambda row: (row["date"], row["id"]))
    start = date.fromisoformat(ordered[0]["date"])
    end = date.fromisoformat(ordered[-1]["date"])
    total = sum(row["value"] for row in ordered)
    by_date: dict[str, list] = defaultdict(list)
    by_category: dict[str, list] = defaultdict(list)
    by_task: dict[str, list] = defaultdict(list)
    for row in ordered:
        by_date[row["date"]].append(row)
        by_category[row["category"]].append(row)
        by_task[row["task_name"]].append(row)

    daily = []
    for offset in range((end - start).days + 1):
        key = (start + timedelta(days=offset)).isoformat()
        entries = by_date.get(key, [])
        daily.append({
            "date": key,
            "record_count": len(entries),
            "total_minutes": sum(row["value"] for row in entries) if entries else None,
            "status": "recorded" if entries else "unrecorded",
        })

    weekly = []
    # Equal seven-calendar-day windows anchored at the fixture's first date.
    for offset in range(0, (end - start).days + 1, 7):
        left = start + timedelta(days=offset)
        right = min(left + timedelta(days=6), end)
        entries = [row for row in ordered if left.isoformat() <= row["date"] <= right.isoformat()]
        totals = {category: sum(row["value"] for row in entries if row["category"] == category)
                  for category in sorted(by_category)}
        weekly.append({
            "start": left.isoformat(), "end": right.isoformat(),
            "record_count": len(entries),
            "total_minutes": sum(row["value"] for row in entries) if entries else None,
            "category_minutes": totals,
        })

    recent_start = end - timedelta(days=6)
    previous_start = end - timedelta(days=13)
    previous_end = end - timedelta(days=7)
    recent = [row for row in ordered if recent_start.isoformat() <= row["date"] <= end.isoformat()]
    previous = [row for row in ordered if previous_start.isoformat() <= row["date"] <= previous_end.isoformat()]
    recent_total = sum(row["value"] for row in recent)
    previous_total = sum(row["value"] for row in previous)
    change = round((recent_total - previous_total) / previous_total * 100, 2) if previous and previous_total else None
    trend = "insufficient_data" if change is None or not recent else (
        "increase" if change > 5 else "decrease" if change < -5 else "stable"
    )

    task_stats = []
    for name, entries in sorted(by_task.items()):
        actual = sum(row["value"] for row in entries)
        estimated = sum(row["estimated_minutes"] for row in entries)
        task_stats.append({
            "task_name": name,
            "category": entries[0]["category"],
            "count": len(entries),
            "total_minutes": actual,
            "average_minutes": round(actual / len(entries), 2),
            "estimated_total_minutes": estimated,
            "average_overrun_minutes": round((actual - estimated) / len(entries), 2),
            "actual_to_estimated_ratio": round(actual / estimated, 3),
        })

    return {
        "source": "synthetic",
        "description": "김실장 개발용 가상 기록의 분석 예시. 실제 사용자의 업무나 성과를 나타내지 않음.",
        "period": {"start": start.isoformat(), "end": end.isoformat(),
                   "calendar_days": (end - start).days + 1},
        "as_of": end.isoformat(),
        "count": len(ordered),
        "recorded_days": len(by_date),
        "unrecorded_days": len(daily) - len(by_date),
        "total_minutes": total,
        "average_minutes_per_record": round(mean(row["value"] for row in ordered), 2),
        "min_minutes": min(row["value"] for row in ordered),
        "max_minutes": max(row["value"] for row in ordered),
        "average_minutes_per_recorded_day": round(total / len(by_date), 2),
        "categories": [
            {"category": category, "count": len(entries),
             "total_minutes": sum(row["value"] for row in entries),
             "share_percent": round(sum(row["value"] for row in entries) / total * 100, 2)}
            for category, entries in sorted(by_category.items())
        ],
        "recent_trend": {
            "basis": "최근 기록일 기준 동일 길이의 7일 구간 총 소요 시간 비교",
            "recent_start": recent_start.isoformat(), "recent_end": end.isoformat(),
            "previous_start": previous_start.isoformat(), "previous_end": previous_end.isoformat(),
            "recent_record_count": len(recent), "previous_record_count": len(previous),
            "recent_total_minutes": recent_total, "previous_total_minutes": previous_total,
            "change_percent": change, "threshold_percent": 5, "direction": trend,
        },
        "daily": daily,
        "weekly": weekly,
        "task_statistics": task_stats,
        "repeat_review_candidates": sorted(
            [row for row in task_stats if row["count"] >= 3],
            key=lambda row: row["total_minutes"], reverse=True,
        ),
        "limitations": [
            "시연을 위해 설계한 패턴이므로 실제 사용자에 대한 결론으로 사용할 수 없음.",
            "기록이 없는 날은 미기록이며 0분 근무나 휴식으로 단정하지 않음.",
            "반복 빈도와 소요 시간만으로 자동화 가능성이나 절감 효과를 확정하지 않음.",
            "전략 상담에는 현재 목표·마감·중요도·선행 작업·가능 시간을 추가로 확인해야 함.",
            "데이터 날짜가 고정되어 있으며 최근 추세는 오늘이 아닌 마지막 기록일을 기준으로 계산함.",
        ],
    }


def make_metadata() -> dict:
    return {
        "dataset_name": "김실장 가상 작업 기록 v1",
        "source": "synthetic",
        "real_personal_data": False,
        "purpose": "M1-2 미션 개발 및 시연",
        "seed": RANDOM_SEED,
        "start": START.isoformat(), "end": END.isoformat(),
        "expected_count": 150,
        "unit": "minutes",
        "timezone": "Asia/Seoul",
        "date_meaning": "가상 사용자가 작업을 수행한 한국 기준 날짜",
        "patterns": [
            "자료 취합: 주차가 지날수록 소요 시간 증가",
            "제안서 작성: 예상 40분을 반복적으로 초과",
            "후반 4주: 창업 검증 준비 대신 지원서 작성에 시간을 배정",
        ],
        "submission_policy": "가상 데이터 제출 허용 확인 완료: 2026-10-28 사용자 확인",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify committed files without modifying them.")
    args = parser.parse_args()
    rows = make_records()
    files = {
        "work_records.json": rows,
        "summary.preview.json": make_summary(rows),
        "dataset_metadata.json": make_metadata(),
    }
    if not args.check:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, value in files.items():
        path = DATA_DIR / name
        content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"Dataset differs: {name}. Regenerate intentionally before committing.")
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
    print(f"{'Verified' if args.check else 'Generated'}: {len(rows)} synthetic records, 56 calendar days.")


if __name__ == "__main__":
    main()
