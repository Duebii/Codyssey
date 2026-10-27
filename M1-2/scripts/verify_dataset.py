"""Independent integrity and planted-pattern checks. Uses no external packages."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    rows = json.loads((DATA_DIR / "work_records.json").read_text(encoding="utf-8"))
    summary = json.loads((DATA_DIR / "summary.preview.json").read_text(encoding="utf-8"))
    metadata = json.loads((DATA_DIR / "dataset_metadata.json").read_text(encoding="utf-8"))
    assert len(rows) == metadata["expected_count"] == 150
    assert len({row["id"] for row in rows}) == len(rows), "Duplicate record IDs"
    assert rows == sorted(rows, key=lambda row: (row["date"], row["id"])), "Records must be chronological"
    daily_totals: dict[str, int] = defaultdict(int)
    for row in rows:
        assert set(row) == {"id", "date", "value", "memo", "task_name", "category", "estimated_minutes", "source"}
        assert date.fromisoformat(row["date"]).isoformat() == row["date"]
        assert metadata["start"] <= row["date"] <= metadata["end"]
        assert type(row["value"]) is int and 0 < row["value"] <= 1440
        assert type(row["estimated_minutes"]) is int and row["estimated_minutes"] > 0
        assert row["category"] in {"프리랜서", "취업", "창업"}
        assert row["source"] == "synthetic"
        assert row["memo"].startswith("시연용:")
        daily_totals[row["date"]] += row["value"]
    assert max(daily_totals.values()) <= 1440
    assert summary["count"] == len(rows)
    assert summary["total_minutes"] == sum(daily_totals.values())
    assert summary["min_minutes"] == min(row["value"] for row in rows)
    assert summary["max_minutes"] == max(row["value"] for row in rows)
    assert summary["average_minutes_per_record"] == round(summary["total_minutes"] / len(rows), 2)
    assert sum(item["total_minutes"] for item in summary["weekly"]) == summary["total_minutes"]
    assert sum(item["total_minutes"] for item in summary["categories"]) == summary["total_minutes"]
    assert len(summary["daily"]) == 56 and summary["recorded_days"] == 40
    assert summary["unrecorded_days"] == 16
    for day in summary["daily"]:
        if day["date"] in daily_totals:
            assert day["total_minutes"] == daily_totals[day["date"]]
        else:
            assert day["total_minutes"] is None and day["status"] == "unrecorded"

    names = Counter(row["task_name"] for row in rows)
    for task in summary["task_statistics"]:
        entries = [row for row in rows if row["task_name"] == task["task_name"]]
        assert task["count"] == names[task["task_name"]]
        assert task["total_minutes"] == sum(row["value"] for row in entries)
    start = date.fromisoformat(metadata["start"])
    collection = [row for row in rows if row["task_name"] == "자료 취합"]
    first_week = [row["value"] for row in collection if row["date"] < (start + timedelta(days=7)).isoformat()]
    last_week = [row["value"] for row in collection if row["date"] >= (start + timedelta(days=49)).isoformat()]
    assert len(first_week) == len(last_week) == 5 and min(last_week) > max(first_week)
    proposals = [row for row in rows if row["task_name"] == "제안서 작성"]
    assert len(proposals) == 20 and all(row["value"] > row["estimated_minutes"] for row in proposals)
    boundary = (start + timedelta(days=28)).isoformat()
    halves = [[row for row in rows if row["date"] < boundary], [row for row in rows if row["date"] >= boundary]]
    shares = [sum(row["value"] for row in half if row["category"] == "취업") / sum(row["value"] for row in half) for half in halves]
    assert shares[1] > shares[0], "Planted job-preparation allocation pattern missing"
    assert metadata["real_personal_data"] is False and summary["source"] == "synthetic"
    print(json.dumps({
        "result": "PASS", "records": len(rows), "recorded_days": len(daily_totals),
        "total_minutes": summary["total_minutes"],
        "collection_first_week_minutes": sum(first_week), "collection_last_week_minutes": sum(last_week),
        "proposal_overrun_records": len(proposals),
        "job_share_first_half_percent": round(shares[0] * 100, 2),
        "job_share_second_half_percent": round(shares[1] * 100, 2),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
