"""Firestore conversation documents; atomic turns and projected history lists."""
from contextlib import contextmanager
import logging
from typing import Callable

from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.firebase import FirebaseClientProvider
from app.repositories.conversations import ConversationConflict, ConversationNotFound
from app.repositories.firestore_records import READ_TIMEOUT, SOURCE, run_firestore_transaction
from app.repositories.records import RepositoryUnavailable

LIST_FIELDS = ("source", "title", "updated_at", "message_count", "last_message_preview")
logger = logging.getLogger("kim_manager.conversations")


class FirestoreConversationRepository:
    def __init__(self, client_provider: Callable | None = None, transaction_runner: Callable | None = None):
        self._provider = client_provider if client_provider is not None else FirebaseClientProvider().get
        self._run_transaction = transaction_runner if transaction_runner is not None else run_firestore_transaction

    @contextmanager
    def _safe_operation(self):
        try:
            yield
        except (RepositoryUnavailable, ConversationNotFound, ConversationConflict):
            raise
        except Exception as exc:
            logger.error("Conversation storage failed (%s)", type(exc).__name__)
            raise RepositoryUnavailable("대화 저장소 처리 결과를 확인할 수 없습니다. 연결 상태를 확인하고 대화를 다시 조회한 뒤 재시도해 주세요.") from None

    @staticmethod
    def _owned(snapshot) -> dict:
        document = snapshot.to_dict() if snapshot.exists else None
        if document is None or document.get("source") != SOURCE:
            raise ConversationNotFound()
        return {**document, "id": snapshot.id}

    def create(self, document: dict) -> dict:
        with self._safe_operation():
            client = self._provider()
            ref = client.collection("conversations").document(document["id"])

            def action(transaction):
                if ref.get(transaction=transaction, timeout=READ_TIMEOUT, retry=None).exists:
                    raise ConversationConflict()
                transaction.create(ref, document)
                return document

            return self._run_transaction(client, action)

    def list_all(self) -> list[dict]:
        with self._safe_operation():
            query = self._provider().collection("conversations").where(filter=FieldFilter("source", "==", SOURCE))
            return [self._owned(snapshot) for snapshot in query.select(LIST_FIELDS).stream(timeout=READ_TIMEOUT, retry=None)]

    def get(self, conversation_id: str) -> dict:
        with self._safe_operation():
            snapshot = self._provider().collection("conversations").document(conversation_id).get(timeout=READ_TIMEOUT, retry=None)
            return self._owned(snapshot)

    def save_turn(self, conversation_id: str, document: dict, expected_revision: int) -> dict:
        with self._safe_operation():
            client = self._provider()
            ref = client.collection("conversations").document(conversation_id)

            def action(transaction):
                current = self._owned(ref.get(transaction=transaction, timeout=READ_TIMEOUT, retry=None))
                revision = current.get("revision")
                if type(revision) is not int or revision < 0:
                    raise RepositoryUnavailable("대화 버전 정보를 확인할 수 없습니다.")
                if revision != expected_revision:
                    raise ConversationConflict()
                transaction.set(ref, document)
                return document

            return self._run_transaction(client, action)

    def delete(self, conversation_id: str) -> None:
        with self._safe_operation():
            client = self._provider()
            ref = client.collection("conversations").document(conversation_id)

            def action(transaction):
                self._owned(ref.get(transaction=transaction, timeout=READ_TIMEOUT, retry=None))
                transaction.delete(ref)

            self._run_transaction(client, action)
