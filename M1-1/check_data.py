"""Audit raw FRED files and create aligned KRW exchange rates (no imputation)."""
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"
START, END = pd.Timestamp("2020-01-01"), pd.Timestamp("2026-08-31")
SERIES = ("DEXKOUS", "DEXUSEU", "DEXJPUS")
LABELS = {"USD_KRW": "1달러당 원화", "EUR_KRW": "1유로당 원화", "JPY100_KRW": "100엔당 원화"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((RAW / "collection_metadata.json").read_text(encoding="utf-8"))
    audits, frames = {}, []
    independent = {}
    for sid in SERIES:
        path = RAW / f"{sid}.csv"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != metadata["series"][sid]["sha256"]:
            raise ValueError(f"{sid}: raw file differs from collection record")
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        if df.columns.tolist() != ["observation_date", sid]:
            raise ValueError(f"{sid}: unexpected columns")
        dates = pd.to_datetime(df["observation_date"], format="%Y-%m-%d", errors="raise")
        vals = pd.to_numeric(df[sid], errors="coerce")
        explicit_missing = df[sid].str.strip().isin(["", "."])
        invalid = vals.isna() & ~explicit_missing
        bad_values = vals.notna() & ((vals <= 0) | ~np.isfinite(vals))
        duplicates = int(dates.duplicated().sum())
        outside = int(((dates < START) | (dates > END)).sum())
        if invalid.any() or bad_values.any() or duplicates or outside:
            raise ValueError(f"{sid}: invalid source data; inspect before cleaning")
        audits[sid] = {
            "rows": len(df), "valid": int(vals.notna().sum()), "missing": int(vals.isna().sum()),
            "duplicates": duplicates, "sorted": bool(dates.is_monotonic_increasing),
            "invalid_numeric": int(invalid.sum()), "nonpositive_or_infinite": int(bad_values.sum()),
            "outside_period": outside, "sha256_matches": True,
            "first_date": dates.min().strftime("%Y-%m-%d"), "last_date": dates.max().strftime("%Y-%m-%d"),
        }
        frames.append(pd.DataFrame({sid: vals.to_numpy()}, index=pd.DatetimeIndex(dates, name="date")))
        with path.open(encoding="utf-8-sig", newline="") as f:
            independent[sid] = {r["observation_date"]: r[sid] for r in csv.DictReader(f)}

    merged = pd.concat(frames, axis=1).sort_index()
    full_dates = pd.date_range(START, END, freq="D", name="date")
    missing_sets = [set(merged.index[merged[s].isna()]) for s in SERIES]
    same_missing = all(missing_sets[0] == x for x in missing_sets[1:])
    unavailable = merged.index[merged.isna().any(axis=1)]
    valid = merged.dropna(subset=list(SERIES))
    if len(valid) < 100:
        raise ValueError("Fewer than 100 common observations")
    absent = full_dates.difference(merged.index)
    absent_weekdays = absent[absent.dayofweek < 5]
    holiday_names = USFederalHolidayCalendar().holidays(start=START, end=END, return_name=True)
    holidays = holiday_names.to_dict()

    date_status = pd.DataFrame(index=full_dates)
    date_status["status"] = [
        "available" if d in valid.index else
        "explicit_missing" if d in merged.index else
        "weekend_not_in_source" if d.dayofweek >= 5 else "weekday_not_in_source"
        for d in full_dates
    ]
    date_status["calendar_match"] = [holidays.get(d, "") for d in full_dates]
    date_status["calendar_note"] = "USFederalHolidayCalendar label is a calendar match, not proof of missing-data cause"
    date_status.to_csv(OUT / "date_status.csv", index_label="date", encoding="utf-8-sig")
    pd.concat([date_status, merged], axis=1).loc[date_status.status != "available"].to_csv(
        OUT / "excluded_dates.csv", index_label="date", encoding="utf-8-sig")

    rates = pd.DataFrame(index=valid.index)
    rates["USD_KRW"] = valid["DEXKOUS"]
    rates["EUR_KRW"] = valid["DEXKOUS"] * valid["DEXUSEU"]
    rates["JPY100_KRW"] = valid["DEXKOUS"] / valid["DEXJPUS"] * 100
    if not np.isfinite(rates.to_numpy()).all() or not (rates > 0).all().all():
        raise ValueError("Invalid derived exchange rates")
    rates.to_csv(OUT / "fx_krw_clean.csv", index_label="date", float_format="%.10f")

    # Check first/middle/last against independent CSV reading and decimal arithmetic.
    samples = []
    for i in [0, len(rates) // 2, len(rates) - 1]:
        day = rates.index[i].strftime("%Y-%m-%d")
        won = Decimal(independent["DEXKOUS"][day])
        euro = won * Decimal(independent["DEXUSEU"][day])
        yen100 = won / Decimal(independent["DEXJPUS"][day]) * 100
        expected = [float(won), float(euro), float(yen100)]
        if not np.allclose(rates.iloc[i].to_numpy(), expected, rtol=0, atol=1e-9):
            raise ValueError(f"Cross-rate mismatch at {day}")
        samples.append({"date": day, **dict(zip(rates.columns, expected))})

    # Use changes rather than price levels so a long-term trend is not mislabeled an outlier.
    changes = rates.pct_change(fill_method=None) * 100
    flags, ranges = [], {}
    for col in rates.columns:
        q1, q3 = changes[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        lower, upper = q1 - 3 * iqr, q3 + 3 * iqr
        selected = changes[col].notna() & ((changes[col] < lower) | (changes[col] > upper))
        ranges[col] = {"lower_change_pct": float(lower), "upper_change_pct": float(upper),
                       "flagged": int(selected.sum())}
        for day in changes.index[selected]:
            idx = rates.index.get_loc(day)
            previous = rates.index[idx - 1]
            flags.append({"date": day.strftime("%Y-%m-%d"), "currency": col,
                          "rate": float(rates.loc[day, col]), "change_pct": float(changes.loc[day, col]),
                          "previous_date": previous.strftime("%Y-%m-%d"),
                          "elapsed_calendar_days": int((day - previous).days),
                          "action": "retain; statistical flag alone does not establish an error"})
    flag_df = pd.DataFrame(flags, columns=["date", "currency", "rate", "change_pct", "previous_date", "elapsed_calendar_days", "action"])
    flag_df.sort_values(["date", "currency"]).to_csv(OUT / "outlier_candidates.csv", index=False)
    calendar_matches = sum(d in holidays for d in unavailable)
    summary = {
        "period": [str(START.date()), str(END.date())], "series": audits,
        "same_missing_dates": same_missing, "common_valid_rows": len(valid),
        "explicit_missing_rows": len(unavailable), "missing_calendar_matches": calendar_matches,
        "missing_without_calendar_match": [str(d.date()) for d in unavailable if d not in holidays],
        "absent_weekdays": [str(d.date()) for d in absent_weekdays],
        "weekends_absent": int(sum(absent.dayofweek >= 5)),
        "calendar_label_source": "pandas.tseries.holiday.USFederalHolidayCalendar",
        "outlier_rule": "observation-to-observation percentage change outside Q1-3*IQR or Q3+3*IQR; retain all candidates",
        "outlier_thresholds": ranges, "decimal_samples": samples,
        "versions": {"pandas": pd.__version__, "numpy": np.__version__},
    }
    (OUT / "data_quality.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 데이터 점검 및 정제 기록", "",
             "분석 범위: 2020-01-01~2026-08-31. 점검 대상은 공식 FRED에서 수집한 세 원본 CSV이다.", "",
             "## 1. 원본 점검", "",
             "| 자료 | 행 수 | 유효 값 | 결측치 | 날짜 중복 | 날짜순 정렬 | 잘못된 숫자 |",
             "|---|---:|---:|---:|---:|---|---:|"]
    for sid, a in audits.items():
        lines.append(f"| {sid} | {a['rows']:,} | {a['valid']:,} | {a['missing']} | {a['duplicates']} | {'예' if a['sorted'] else '아니오'} | {a['invalid_numeric'] + a['nonpositive_or_infinite']} |")
    lines += ["", "- 세 원본 모두 수집 기록의 SHA-256 해시와 일치한다. 복사 과정에서 값이 바뀌지 않았다.",
              f"- 실제 원본 날짜 범위: {valid.index.min():%Y-%m-%d}~{valid.index.max():%Y-%m-%d}.",
              f"- 세 자료의 결측 날짜 동일 여부: {'동일' if same_missing else '다름'}.",
              "", "## 2. 결측치와 비관측일", "",
              f"원본에 존재하지만 값이 비어 있는 날짜는 {len(unavailable)}개다. 주말처럼 원본에 행 자체가 없는 날과 구분한다.",
              f"요청 기간의 주말 중 원본에 없는 날짜는 {summary['weekends_absent']}개, 평일 중 원본에 없는 날짜는 {len(absent_weekdays)}개다.",
              f"평일 비관측 날짜: {', '.join(summary['absent_weekdays']) or '없음'}.",
              f"원본 결측 날짜 중 미국 연방 공휴일 달력과 일치하는 날짜는 {calendar_matches}개, 일치하지 않는 날짜는 {len(unavailable)-calendar_matches}개다.",
              f"달력과 일치하지 않는 결측 날짜: {', '.join(summary['missing_without_calendar_match']) or '없음'}.",
              "달력 일치는 원인 추정의 근거이며, 각 날짜의 결측 원인을 확정한 결과가 아니다. 일치하지 않는 날짜의 원인은 미확인으로 남긴다.",
              "연준의 [공식 휴일 안내](https://www.federalreserve.gov/aboutthefed/k8.htm)는 대체휴일과 연준 이사회/은행의 휴일 차이를 설명한다. 2026~2030년 안내이므로 과거 모든 결측 원인을 설명하는 자료로 사용하지 않는다.",
              "", "**처리:** 원본은 그대로 보존하고 세 자료가 모두 유효한 날짜만 분석에 사용한다. 결측치를 0으로 바꾸거나 전날 값으로 채우지 않는다. 채우면 인위적인 0% 변화가 생겨 변동성을 작게 보이게 할 수 있다.",
              f"최종 분석용 데이터는 {len(rates):,}행이며, 각 통화에 동일한 날짜를 적용한다. 제외 날짜는 [excluded_dates.csv](excluded_dates.csv)에 기록했다.",
              "", "## 3. 단위 환산 및 계산 검증", "",
              "- USD_KRW: DEXKOUS 그대로, 1달러당 원화.",
              "- EUR_KRW: DEXKOUS × DEXUSEU, 1유로당 원화.",
              "- JPY100_KRW: DEXKOUS ÷ DEXJPUS × 100, 100엔당 원화.",
              "유로와 엔화는 같은 날짜의 원자료로 계산한 교차환율이다. 국내 고객 환전율, 수수료 또는 국내 종가를 뜻하지 않는다.",
              "첫·중간·마지막 관측일을 별도 CSV 읽기와 Decimal 계산으로 대조했다. 표시값은 소수 둘째 자리까지지만 분석용 CSV는 소수 열 자리까지 보존한다.",
              "", "| 날짜 | 원/1달러 | 원/1유로 | 원/100엔 |", "|---|---:|---:|---:|"]
    lines += [f"| {s['date']} | {s['USD_KRW']:,.2f} | {s['EUR_KRW']:,.2f} | {s['JPY100_KRW']:,.2f} |" for s in samples]
    lines += ["", "## 4. 이상치 후보 점검", "",
              "큰 숫자라는 이유로 삭제하지 않는다. 가격 수준 대신 전 관측일 대비 변화율을 사용하고, Q1−3×IQR 미만 또는 Q3+3×IQR 초과를 검토 후보로 표시한다. 이 기준은 오류를 확정하는 규칙이 아니며, 해당 구간의 실제 시장 움직임은 이후 분석에서 검토한다.",
              "", "| 통화 | 변화율 하한(%) | 변화율 상한(%) | 후보 수 | 처리 |", "|---|---:|---:|---:|---|"]
    for col, a in ranges.items():
        lines.append(f"| {LABELS[col]} | {a['lower_change_pct']:.4f} | {a['upper_change_pct']:.4f} | {a['flagged']} | 유지 |")
    lines += ["", "전 관측일과의 차이는 주말·휴일을 포함한 여러 달력 날짜의 변화일 수 있다. 후보 목록에 경과 날짜 수를 함께 기록했다.",
              "", "## 5. 생성 파일과 다음 단계", "",
              "- [분석용 환율 데이터](fx_krw_clean.csv)", "- [날짜별 상태](date_status.csv)",
              "- [제외 날짜](excluded_dates.csv)", "- [이상치 후보](outlier_candidates.csv)",
              "- [점검 결과 JSON](data_quality.json)",
              "", "이 단계는 데이터 준비다. 다음 단계에서 시작값 100 비교, 20개 관측일 이동평균, 월별 변화율 표준편차를 계산한다.",
              "", "## 6. AI 사용 로그", "",
              "| 사용 작업 | 사용 이유 | 검증 방법 |", "|---|---|---|",
              "| 점검 코드와 정제 기록 작성 | 반복 검사와 계산을 재현하기 위해 | 코드 실행, 원본 해시 확인, 독립 Decimal 표본 계산 |",
              "| 결측치·이상치 처리 기준 제안 | 인위적인 값 채우기와 자동 삭제의 영향을 검토하기 위해 | 세 자료의 결측 날짜 대조, 휴일 달력 대조, 후보를 원본 그대로 유지 |",
              "휴일 원인 추정과 실제 이상치 후보의 사건 해석은 확정되지 않았다. 최종 해석은 사용자 검토가 필요하다.",
              "", "## 7. 데이터 출처", "",
              "원출처: Board of Governors of the Federal Reserve System (US), H.10 Foreign Exchange Rates. 제공: FRED, Federal Reserve Bank of St. Louis.",
              "- [DEXKOUS](https://fred.stlouisfed.org/series/DEXKOUS)",
              "- [DEXUSEU](https://fred.stlouisfed.org/series/DEXUSEU)",
              "- [DEXJPUS](https://fred.stlouisfed.org/series/DEXJPUS)",
              "관측 기준: 뉴욕 정오, 일별, 계절조정하지 않음. 원본 수집 시각은 data/raw/collection_metadata.json에 기록되어 있다.",
              "각 시리즈 페이지의 Public Domain: Citation Requested 표시에 따라 출처를 명시한다.", ""]
    (OUT / "DATA_CHECK.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["common_valid_rows", "same_missing_dates", "explicit_missing_rows", "missing_calendar_matches", "missing_without_calendar_match", "absent_weekdays", "weekends_absent", "outlier_thresholds", "decimal_samples"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
