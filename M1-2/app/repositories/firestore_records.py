"""Real Firestore adapter. Test clients/runners are injected only by tests."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.firebase import FirebaseClientProvider
from app.repositories.records import DailyLimitExceeded, RecordConflict, RecordNotFound, RepositoryUnavailable
from app.repositories.summaries import RecordSnapshot, SummaryState

SOURCE = "synthetic"
READ_TIMEOUT = 10
logger = logging.getLogger("kim_manager.storage")


def run_firestore_transaction(client, action):
    from firebase_admin import firestore

    transaction = client.transaction(max_attempts=3)
    return firestore.transactional(action)(transaction)


class FirestoreRecordRepository:
    def __init__(self, client_provider: Callable | None = None, transaction_runner: Callable | None = None):
        self._provider = client_provider if client_provider is not None else FirebaseClientProvider().get
        self._run_transaction = transaction_runner if transaction_runner is not None else run_firestore_transaction

    @contextmanager
    def _safe_operation(self):
        try:
            yield
        except (RepositoryUnavailable, RecordNotFound, RecordConflict, DailyLimitExceeded):
            raise
        except Exception as exc:
            logger.error("Firestore operation failed (%s)", type(exc).__name__)
            raise RepositoryUnavailable(
                "Firestore 처리 결과를 확인할 수 없습니다. 프로젝트·데이터베이스·권한·연결 상태를 확인하고, 목록을 다시 조회한 뒤 재시도해 주세요."
            ) from None

    @staticmethod
    def _item(snapshot) -> dict:
        return {**snapshot.to_dict(), "id": snapshot.id}

    @staticmethod
    def _query(client, day: str | None = None):
        query = client.collection("data").where(filter=FieldFilter("source", "==", SOURCE))
        return query.where(filter=FieldFilter("date", "==", day)) if day is not None else query

    def list_all(self) -> list[dict]:
        with self._safe_operation():
            client = self._provider()
            items = [self._item(snapshot) for snapshot in self._query(client).stream(timeout=READ_TIMEOUT, retry=None)]
            # Sort in Python for this small dataset; avoid a composite ordering index.
            items.sort(key=lambda item: item["id"])
            items.sort(key=lambda item: item["date"], reverse=True)
            return items

    @staticmethod
    def _revision(snapshot) -> int:
        revision = (snapshot.to_dict() or {}).get("data_revision", 0) if snapshot.exists else 0
        if type(revision) is not int or revision < 0:
            raise RepositoryUnavailable("기록 버전 정보를 확인할 수 없습니다. 저장소 상태를 확인해 주세요.")
        return revision

    def summary_state(self) -> SummaryState:
        with self._safe_operation():
            client = self._provider()

            def action(transaction):
                metadata = client.collection("metadata").document(SOURCE).get(
                    transaction=transaction, timeout=READ_TIMEOUT, retry=None,
                )
                cached = client.collection("summaries").document(SOURCE).get(
                    transaction=transaction, timeout=READ_TIMEOUT, retry=None,
                )
                values = metadata.to_dict() or {}
                return SummaryState(self._revision(metadata), values.get("summary_stale") is not False,
                                    cached.to_dict() if cached.exists else None)

            return self._run_transaction(client, action)

    def summary_snapshot(self) -> RecordSnapshot:
        with self._safe_operation():
            client = self._provider()

            def action(transaction):
                metadata = client.collection("metadata").document(SOURCE).get(
                    transaction=transaction, timeout=READ_TIMEOUT, retry=None,
                )
                items = [self._item(snapshot) for snapshot in self._query(client).stream(
                    transaction=transaction, timeout=READ_TIMEOUT, retry=None,
                )]
                return RecordSnapshot(self._revision(metadata), items)

            return self._run_transaction(client, action)

    def save_summary_if_current(self, document: dict) -> bool:
        with self._safe_operation():
            client = self._provider()
            metadata_ref = client.collection("metadata").document(SOURCE)

            def action(transaction):
                metadata = metadata_ref.get(transaction=transaction, timeout=READ_TIMEOUT, retry=None)
                if self._revision(metadata) != document["data_revision"]:
                    return False
                transaction.set(client.collection("summaries").document(SOURCE), document)
                transaction.set(metadata_ref, {"source": SOURCE, "data_revision": document["data_revision"],
                                               "summary_stale": False}, merge=True)
                return True

            return self._run_transaction(client, action)

    def _mutate(self, operation: str, record_id: str, payload: dict | None = None, *, skip_existing: bool = False):
        with self._safe_operation():
            client = self._provider()
            record_ref = client.collection("data").document(record_id)
            metadata_ref = client.collection("metadata").document(SOURCE)
            now = datetime.now(timezone.utc).isoformat()

            def action(transaction):
                # Every writer reads and updates this same revision document.
                # Concurrent writes conflict and retry before the daily cap is accepted.
                metadata = metadata_ref.get(transaction=transaction, timeout=READ_TIMEOUT, retry=None)
                current = record_ref.get(transaction=transaction, timeout=READ_TIMEOUT, retry=None)
                existing = current.to_dict() if current.exists else None
                if operation == "create" and existing is not None:
                    if existing.get("source") != SOURCE or not skip_existing:
                        raise RecordConflict()
                    return None
                if operation != "create" and (existing is None or existing.get("source") != SOURCE):
                    raise RecordNotFound()
                revision = self._revision(metadata)

                if operation != "delete":
                    day_records = list(self._query(client, payload["date"]).stream(
                        transaction=transaction, timeout=READ_TIMEOUT, retry=None,
                    ))
                    total = sum(snapshot.to_dict()["value"] for snapshot in day_records if snapshot.id != record_id)
                    if total + payload["value"] > 1440:
                        raise DailyLimitExceeded()
                    item = {
                        **payload, "id": record_id, "source": SOURCE,
                        "created_at": now if operation == "create" else existing["created_at"],
                        "updated_at": now,
                    }
                    if operation == "create":
                        transaction.create(record_ref, item)
                    else:
                        transaction.set(record_ref, item)
                else:
                    transaction.delete(record_ref)
                    item = None
                transaction.set(metadata_ref, {
                    "source": SOURCE, "data_revision": revision + 1,
                    "summary_stale": True, "updated_at": now,
                }, merge=True)
                return item

            return self._run_transaction(client, action)

    def create(self, payload: dict, *, record_id: str | None = None, skip_existing: bool = False) -> dict | None:
        return self._mutate("create", record_id or uuid4().hex, payload, skip_existing=skip_existing)

    def update(self, record_id: str, payload: dict) -> dict:
        return self._mutate("update", record_id, payload)

    def delete(self, record_id: str) -> None:
        self._mutate("delete", record_id)
