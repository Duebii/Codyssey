"""Download official FRED FX data; preserve raw bytes and validate coverage.

Python 3.10+, standard library only. Run: python collect_data.py
If CSVs were downloaded manually, run: python collect_data.py --local
"""
import argparse
import csv
import hashlib
import io
import json
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
START, END = "2020-01-01", "2026-08-31"
SERIES = {
    "DEXKOUS": "KRW per USD",
    "DEXUSEU": "USD per EUR",
    "DEXJPUS": "JPY per USD",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true", help="Use manually downloaded raw CSV files")
    args = parser.parse_args()
    raw = ROOT / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    metadata = {"requested_start": START, "requested_end": END,
                "checked_at_utc": datetime.now(timezone.utc).isoformat(), "series": {}}
    for sid, unit in SERIES.items():
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={START}&coed={END}"
        path = raw / f"{sid}.csv"
        if not args.local:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (educational time-series analysis)"})
            with urlopen(req, timeout=45) as response:
                payload = response.read()
        else:
            payload = path.read_bytes()
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        if not reader.fieldnames or sid not in reader.fieldnames:
            raise ValueError(f"{sid}: Expected a FRED CSV with a {sid} column")
        date_col = reader.fieldnames[0]
        dates, valid, missing = [], [], []
        for row in reader:
            day = date.fromisoformat(row[date_col]).isoformat()
            if START <= day <= END:
                dates.append(day)
                if row[sid].strip() in ("", "."):
                    missing.append(day)
                else:
                    value = float(row[sid])
                    if not 0 < value < float("inf"):
                        raise ValueError(f"{sid}: Invalid value on {day}")
                    valid.append(day)
        if len(dates) != len(set(dates)):
            raise ValueError(f"{sid}: Duplicate dates")
        if len(valid) < 100:
            raise ValueError(f"{sid}: Fewer than 100 valid observations")
        if min(valid) > "2020-01-07" or max(valid) < "2026-08-28":
            raise ValueError(f"{sid}: Requested period not adequately covered: {min(valid)} to {max(valid)}")
        if not args.local:
            path.write_bytes(payload)
        metadata["series"][sid] = {
            "page": f"https://fred.stlouisfed.org/series/{sid}",
            "download_url": url, "unit": unit, "method": "manual CSV" if args.local else "direct download",
            "rows_in_period": len(dates), "valid_observations": len(valid),
            "first_valid_date": min(valid), "last_valid_date": max(valid),
            "missing_dates": missing, "sha256": hashlib.sha256(payload).hexdigest(),
        }
        print(f"{sid}: {len(valid)} valid observations, {len(missing)} missing, {min(valid)} to {max(valid)}")
    (raw / "collection_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Collection and basic validation complete. Raw CSVs preserved.")


if __name__ == "__main__":
    main()
