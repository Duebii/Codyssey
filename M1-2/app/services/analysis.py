"""Deterministic time-series analysis. No database or model calls."""
from collections import defaultdict
from datetime import date, timedelta

from app.schemas.records import RecordInput

MAX_CALENDAR_DAYS = 3660
LIMITATIONS = [
    "가상 데이터이므로 실제 사용자의 업무나 성과에 대한 결론으로 사용할 수 없음.",
    "기록이 없는 날은 미기록이며 0분 근무나 휴식으로 단정하지 않음.",
    "반복 빈도와 소요 시간만으로 자동화 가능성이나 절감 효과를 확정하지 않음.",
    "전략 상담에는 현재 목표·마감·중요도·선행 작업·가능 시간을 추가로 확인해야 함.",
    "최근 추세는 오늘이 아닌 마지막 기록일을 기준으로 기록된 총 시간을 비교함.",
]


def _before(day: date, days: int) -> str | None:
    return (day - timedelta(days=days)).isoformat() if (day - date.min).days >= days else None


def analyze_records(records: list[dict]) -> dict:
    rows = []
    for record in records:
        if record.get("source") != "synthetic":
            raise ValueError("Unexpected record source")
        row = RecordInput.model_validate({key: record[key] for key in RecordInput.model_fields if key in record})
        rows.append(row.model_dump(mode="json"))
    rows.sort(key=lambda row: row["date"])
    trend = {"basis": "최근 기록일 기준 동일 길이의 7일 구간 총 소요 시간 비교",
             "recent_start": None, "recent_end": None, "previous_start": None, "previous_end": None,
             "recent_record_count": 0, "previous_record_count": 0,
             "recent_recorded_days": 0, "previous_recorded_days": 0,
             "recent_total_minutes": 0, "previous_total_minutes": 0,
             "change_percent": None, "threshold_percent": 5, "direction": "insufficient_data"}
    result = {"source": "synthetic", "description": "Firestore의 가상 작업 기록을 분석한 요약. 실제 사용자의 업무나 성과를 나타내지 않음.",
              "period": None, "as_of": None, "count": len(rows), "recorded_days": 0, "unrecorded_days": 0,
              "total_minutes": 0, "average_minutes_per_record": None, "min_minutes": None, "max_minutes": None,
              "average_minutes_per_recorded_day": None, "categories": [], "recent_trend": trend,
              "daily": [], "weekly": [], "task_statistics": [], "repeat_review_candidates": [],
              "limitations": list(LIMITATIONS)}
    if not rows:
        return result
    start, end = date.fromisoformat(rows[0]["date"]), date.fromisoformat(rows[-1]["date"])
    calendar_days = (end - start).days + 1
    if calendar_days > MAX_CALENDAR_DAYS:
        raise ValueError("Summary period exceeds bounded daily analysis")
    by_date, by_category, by_task = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in rows:
        by_date[row["date"]].append(row)
        by_category[row["category"]].append(row)
        by_task[(row["task_name"], row["category"])].append(row)
    if any(sum(row["value"] for row in entries) > 1440 for entries in by_date.values()):
        raise ValueError("Stored records exceed daily time limit")
    total = sum(row["value"] for row in rows)
    result.update(period={"start": start.isoformat(), "end": end.isoformat(), "calendar_days": calendar_days},
                  as_of=end.isoformat(), recorded_days=len(by_date), unrecorded_days=calendar_days - len(by_date),
                  total_minutes=total, average_minutes_per_record=round(total / len(rows), 2),
                  min_minutes=min(row["value"] for row in rows), max_minutes=max(row["value"] for row in rows),
                  average_minutes_per_recorded_day=round(total / len(by_date), 2))
    for category, entries in sorted(by_category.items()):
        minutes = sum(row["value"] for row in entries)
        result["categories"].append({"category": category, "count": len(entries), "total_minutes": minutes,
                                     "share_percent": round(minutes / total * 100, 2)})
    for offset in range(calendar_days):
        day = (start + timedelta(days=offset)).isoformat()
        entries = by_date.get(day, [])
        result["daily"].append({"date": day, "record_count": len(entries),
                                "total_minutes": sum(row["value"] for row in entries) if entries else None,
                                "status": "recorded" if entries else "unrecorded"})
    for offset in range(0, calendar_days, 7):
        days = result["daily"][offset:offset + 7]
        entries = [row for day in days for row in by_date.get(day["date"], [])]
        recorded = sum(day["status"] == "recorded" for day in days)
        result["weekly"].append({"start": days[0]["date"], "end": days[-1]["date"], "calendar_days": len(days),
                                 "is_partial": len(days) < 7, "record_count": len(entries), "recorded_days": recorded,
                                 "unrecorded_days": len(days) - recorded,
                                 "total_minutes": sum(row["value"] for row in entries) if entries else None,
                                 "category_minutes": {category: sum(row["value"] for row in entries if row["category"] == category)
                                                      for category in sorted(by_category)}})
    trend.update(recent_start=_before(end, 6), recent_end=end.isoformat(),
                 previous_start=_before(end, 13), previous_end=_before(end, 7))
    recent = [row for row in rows if row["date"] >= (trend["recent_start"] or date.min.isoformat())]
    previous = [row for row in rows if trend["previous_end"] is not None
                and (trend["previous_start"] or date.min.isoformat()) <= row["date"] <= trend["previous_end"]]
    recent_total, previous_total = sum(row["value"] for row in recent), sum(row["value"] for row in previous)
    trend.update(recent_record_count=len(recent), previous_record_count=len(previous),
                 recent_recorded_days=len({row["date"] for row in recent}), previous_recorded_days=len({row["date"] for row in previous}),
                 recent_total_minutes=recent_total, previous_total_minutes=previous_total)
    if calendar_days >= 14 and recent and previous and previous_total:
        delta = recent_total - previous_total
        trend.update(change_percent=round(delta / previous_total * 100, 2),
                     direction="increase" if delta * 100 > previous_total * 5 else
                               "decrease" if delta * 100 < -previous_total * 5 else "stable")
    for (name, category), entries in sorted(by_task.items()):
        actual = sum(row["value"] for row in entries)
        paired = [row for row in entries if row["estimated_minutes"] is not None]
        paired_actual = sum(row["value"] for row in paired)
        estimated = sum(row["estimated_minutes"] for row in paired)
        result["task_statistics"].append({"task_name": name, "category": category, "count": len(entries),
            "total_minutes": actual, "average_minutes": round(actual / len(entries), 2), "paired_count": len(paired),
            "paired_actual_total_minutes": paired_actual, "estimated_total_minutes": estimated if paired else None,
            "average_overrun_minutes": round((paired_actual - estimated) / len(paired), 2) if paired else None,
            "actual_to_estimated_ratio": round(paired_actual / estimated, 3) if paired else None})
    result["repeat_review_candidates"] = sorted([row for row in result["task_statistics"] if row["count"] >= 3],
                                                key=lambda row: (-row["total_minutes"], row["task_name"], row["category"]))
    return result
