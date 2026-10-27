"""Validate by default; use --apply only after Firebase setup is complete."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.repositories.firestore_records import FirestoreRecordRepository
from app.repositories.records import DailyLimitExceeded, RecordConflict, RepositoryUnavailable
from app.services.import_records import import_records, prepare_import


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write missing synthetic records to the configured Firestore project.")
    args = parser.parse_args()
    try:
        records = prepare_import(PROJECT_ROOT / "data" / "work_records.json")
    except Exception:
        print("가져오기 파일 검증 실패: JSON·출처·ID·날짜·시간·하루 합계를 확인해 주세요. 원본 값은 출력하지 않습니다.")
        return 1
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "source": "synthetic", "records": len(records),
                          "total_minutes": sum(record.value for record in records),
                          "external_connections": 0, "writes": 0}, ensure_ascii=False, indent=2))
        print("검증만 완료했습니다. 실제 Firestore 저장은 외부 설정 후 --apply로 실행합니다.")
        return 0
    try:
        result = import_records(FirestoreRecordRepository(), records)
    except (DailyLimitExceeded, RecordConflict):
        print("가져오기를 중단했습니다. 기존 기록의 출처·ID 충돌 또는 하루 시간 한도를 확인해 주세요. 이전에 저장된 건은 유지됩니다.")
        return 1
    except RepositoryUnavailable:
        print("Firestore 설정 또는 처리 결과를 확인할 수 없습니다. 로컬 인증 설정·프로젝트·DB·권한을 확인하세요. 일부 저장 가능성이 있으면 목록을 확인하고 재실행하세요.")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
