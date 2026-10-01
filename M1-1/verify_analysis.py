"""Independently verify exported calculations with Decimal and statistics.

Uses the Python standard library; does not import pandas or numpy.
Run after check_data.py and analysis.py: python verify_analysis.py
"""
import csv
import hashlib
import json
import math
import re
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
COLS = ("USD_KRW", "EUR_KRW", "JPY100_KRW")


def table(path, key):
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    keys = [r[key] for r in rows]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise ValueError(f"{path.name}: unordered or duplicate keys")
    return {r[key]: r for r in rows}


def near(actual, expected, label, tolerance=1e-8):
    if not math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=tolerance):
        raise ValueError(f"{label}: {actual} != {expected}")


def main():
    metadata = json.loads((ROOT / "data/raw/collection_metadata.json").read_text(encoding="utf-8"))
    raw = {}
    for sid in ("DEXKOUS", "DEXUSEU", "DEXJPUS"):
        p = ROOT / "data/raw" / f"{sid}.csv"
        if hashlib.sha256(p.read_bytes()).hexdigest() != metadata["series"][sid]["sha256"]:
            raise ValueError(f"{sid}: hash mismatch")
        raw[sid] = table(p, "observation_date")
    dates = sorted(set.intersection(*(set(raw[s]) for s in raw)))
    dates = [d for d in dates if all(raw[s][d][s].strip() not in ("", ".") for s in raw)]
    values = {c: [] for c in COLS}
    for day in dates:
        w = Decimal(raw["DEXKOUS"][day]["DEXKOUS"])
        e = w * Decimal(raw["DEXUSEU"][day]["DEXUSEU"])
        y = w / Decimal(raw["DEXJPUS"][day]["DEXJPUS"]) * 100
        for c, val in zip(COLS, (w, e, y)):
            values[c].append(val)
    clean = table(OUT / "fx_krw_clean.csv", "date")
    index = table(OUT / "fx_index100.csv", "date")
    ma = table(OUT / "fx_ma20.csv", "date")
    changes = table(OUT / "fx_change_pct.csv", "date")
    vol = table(OUT / "monthly_volatility.csv", "month")
    counts = table(OUT / "monthly_change_counts.csv", "month")
    summary = json.loads((OUT / "analysis_summary.json").read_text(encoding="utf-8"))
    for t in (clean, index, ma, changes):
        if list(t) != dates:
            raise ValueError("Exported dates do not match common raw observations")
    num_checks = 0
    for c in COLS:
        by_month = defaultdict(list)
        all_changes = []
        for i, day in enumerate(dates):
            v = values[c][i]
            near(clean[day][c], v, f"{c} {day} rate", 1e-9)
            near(index[day][c], v / values[c][0] * 100, f"{c} {day} index")
            num_checks += 2
            if i < 19:
                if ma[day][c] != "":
                    raise ValueError("Moving average must be unavailable before 20 observations")
            else:
                expected_ma = sum(values[c][i-19:i+1]) / 20
                near(ma[day][c], expected_ma, f"{c} {day} moving average")
                num_checks += 1
            if i == 0:
                if changes[day][c] != "":
                    raise ValueError("First percentage change must be unavailable")
            else:
                pct = float((v / values[c][i-1] - 1) * 100)
                near(changes[day][c], pct, f"{c} {day} change")
                by_month[day[:7] + "-01"].append(pct)
                all_changes.append(pct)
                num_checks += 1
        if list(vol) != sorted(by_month):
            raise ValueError("Volatility month mismatch")
        monthly_expected = {}
        for month, vals in by_month.items():
            sd = statistics.stdev(vals)
            monthly_expected[month] = sd
            near(vol[month][c], sd, f"{c} {month} std")
            if int(counts[month][c]) != len(vals):
                raise ValueError("Monthly valid-change count mismatch")
            num_checks += 2
        m = summary["metrics"][c]
        near(m["first_rate"], values[c][0], c + " first")
        near(m["last_rate"], values[c][-1], c + " last")
        near(m["change_pct"], (values[c][-1] / values[c][0] - 1) * 100, c + " total")
        near(m["minimum"], min(values[c]), c + " minimum")
        near(m["maximum"], max(values[c]), c + " maximum")
        near(m["change_std_full_period"], statistics.stdev(all_changes), c + " full std")
        peak_month = max(monthly_expected, key=monthly_expected.get)
        if m["peak_volatility_month"] != peak_month[:7]:
            raise ValueError("Peak volatility month mismatch")
        near(m["peak_monthly_volatility_pct"], monthly_expected[peak_month], c + " peak std")
        if m["minimum_date"] != dates[values[c].index(min(values[c]))] or m["maximum_date"] != dates[values[c].index(max(values[c]))]:
            raise ValueError("Extrema dates mismatch")
        num_checks += 7
    report_sections = ["분석 주제", "분석 질문", "데이터", "시각화", "인사이트", "결론", "한계", "AI 사용 로그"]
    report = OUT / "REPORT.md"
    if not report.exists():
        raise ValueError("REPORT.md is required for final verification")
    text = report.read_text(encoding="utf-8")
    if not all(s in text for s in report_sections):
        raise ValueError("Required report section is missing")
    local_links = 0
    # Personal working notes may remain locally; verify the published analysis docs.
    for path in [report, OUT / "DATA_CHECK.md", OUT / "ANALYSIS_NOTES.md", ROOT / "README.md"]:
        for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if link.startswith(("https://", "http://", "#")):
                continue
            target = path.parent / link.split("#")[0]
            # The verification record is created only after every check passes.
            if target.resolve() != (OUT / "verification.json").resolve() and not target.exists():
                raise ValueError(f"Broken link in {path.name}: {link}")
            local_links += 1
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    if len(images) < 3:
        raise ValueError("Report must contain at least 3 charts")
    for img in images:
        if (report.parent / img).read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Expected a PNG image")
    result = {"status": "passed", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "method": "independent raw CSV read, Decimal arithmetic, statistics.stdev",
              "common_observations": len(dates), "currency_series": 3, "monthly_periods": len(vol),
              "numeric_checks": num_checks, "local_links_checked": local_links,
              "report_images": len(images), "export_tolerance_absolute": 1e-8,
              "raw_hashes_match": True}
    (OUT / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
