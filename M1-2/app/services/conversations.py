"""Conversation CRUD and atomic user/assistant turn persistence."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from uuid import uuid4

from pydantic import ValidationError

from app.core.errors import ApiError
from app.repositories.conversations import (
    ConversationConflict, ConversationLimitExceeded, ConversationNotFound,
    ConversationRepository, ConversationTooLarge,
)
from app.repositories.records import RepositoryUnavailable
from app.schemas.conversations import (
    ContextPatch, ConversationInput, StoredConversation, StoredConversationListItem, TurnInput,
)

MAX_MESSAGES = 100
MAX_CONTENT_CHARACTERS = 60_000
MAX_DOCUMENT_BYTES = 500 * 1024
INTERNAL_FIELDS = {"schema_version", "title_is_custom", "message_count", "last_message_preview"}


def enforce_limits(document: dict) -> None:
    messages = document["messages"]
    if len(messages) > MAX_MESSAGES or sum(len(message["content"]) for message in messages) > MAX_CONTENT_CHARACTERS:
        raise ConversationLimitExceeded()
    if len(json.dumps(document, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise ConversationTooLarge()


class ConversationService:
    def __init__(self, repository: ConversationRepository):
        self.repository = repository

    @contextmanager
    def _errors(self):
        try:
            yield
        except ConversationNotFound:
            raise ApiError(404, "not_found", "해당 가상 상담을 찾을 수 없습니다.") from None
        except ConversationConflict:
            raise ApiError(409, "conversation_conflict", "대화가 변경됐거나 이미 존재합니다. 최신 대화를 다시 불러온 뒤 재시도해 주세요.") from None
        except ConversationLimitExceeded:
            raise ApiError(409, "conversation_limit", "대화는 최대 100개 메시지·본문 총 60,000자까지 저장할 수 있습니다. 새 상담을 시작해 주세요.") from None
        except ConversationTooLarge:
            raise ApiError(413, "payload_too_large", "대화 저장 크기 500KiB를 초과했습니다. 새 상담을 시작해 주세요.") from None
        except RepositoryUnavailable as exc:
            raise ApiError(503, "storage_unavailable", str(exc)) from None
        except (ValidationError, ValueError, TypeError, UnicodeError):
            raise ApiError(422, "invalid_request", "상담 조건과 메시지 형식·범위를 확인해 주세요.") from None

    @staticmethod
    def _stored(document: dict) -> StoredConversation:
        try:
            enforce_limits(document)
            stored = StoredConversation.model_validate(document)
            enforce_limits(stored.model_dump(mode="json"))
            return stored
        except Exception:
            raise RepositoryUnavailable("저장된 대화의 구조·메시지·크기를 확인할 수 없습니다.") from None

    @staticmethod
    def _response(stored: StoredConversation) -> dict:
        return {"conversation": stored.model_dump(mode="json", exclude=INTERNAL_FIELDS)}

    def create(self, payload: ConversationInput) -> dict:
        with self._errors():
            now = datetime.now(timezone.utc)
            stored = StoredConversation(id=uuid4().hex, title=payload.title, source="synthetic",
                created_at=now, updated_at=now, mode=payload.mode, context=payload.context,
                revision=0, messages=[], title_is_custom="title" in payload.model_fields_set,
                message_count=0, last_message_preview="")
            document = stored.model_dump(mode="json")
            enforce_limits(document)
            return self._response(self._stored(self.repository.create(document)))

    def list(self, page: int, page_size: int) -> dict:
        with self._errors():
            try:
                items = [StoredConversationListItem.model_validate(item) for item in self.repository.list_all()]
            except ValidationError:
                raise RepositoryUnavailable("저장된 대화 목록의 구조를 확인할 수 없습니다.") from None
            items.sort(key=lambda item: item.id)
            items.sort(key=lambda item: item.updated_at, reverse=True)
            start = (page - 1) * page_size
            return {"items": [item.model_dump(mode="json", exclude={"source"}) for item in items[start:start + page_size]],
                    "total": len(items), "page": page, "page_size": page_size}

    def get(self, conversation_id: str) -> dict:
        with self._errors():
            return self._response(self._stored(self.repository.get(conversation_id)))

    def prepare_chat(self, conversation_id: str | None, user_content: str) -> StoredConversation:
        """Read storage and check known limits before any paid request; no writes."""
        with self._errors():
            if conversation_id is None:
                now = datetime.now(timezone.utc)
                current = StoredConversation(id=uuid4().hex, title="새 상담", source="synthetic",
                    created_at=now, updated_at=now, mode="strategy", context=ContextPatch(), revision=0,
                    messages=[], title_is_custom=False, message_count=0, last_message_preview="")
                try:
                    self.repository.get(current.id)
                except ConversationNotFound:
                    return current
                raise ConversationConflict()
            current = self._stored(self.repository.get(conversation_id))
            if len(current.messages) + 2 > MAX_MESSAGES or sum(len(item.content) for item in current.messages) + len(user_content) >= MAX_CONTENT_CHARACTERS:
                raise ConversationLimitExceeded()
            return current

    @staticmethod
    def _append_turn(current: StoredConversation, turn: TurnInput) -> dict:
        context_values = current.context.model_dump(mode="json")
        if turn.context is not None:
            context_values.update(turn.context.model_dump(mode="json", exclude_unset=True))
        context = ContextPatch.model_validate(context_values).model_dump(mode="json")
        mode = turn.mode or current.mode
        now = datetime.now(timezone.utc).isoformat()
        common = {"created_at": now, "mode": mode, "context": context}
        pair = [
            {"id": uuid4().hex, "role": "user", "content": turn.user_content, **common},
            {"id": uuid4().hex, "role": "assistant", **turn.assistant.model_dump(mode="json"), **common},
        ]
        document = current.model_dump(mode="json")
        document.update(messages=[*document["messages"], *pair], mode=mode, context=context,
                        updated_at=now, revision=current.revision + 1, message_count=current.message_count + 2,
                        last_message_preview=turn.assistant.content[:100].strip())
        if not current.title_is_custom and not current.messages:
            document["title"] = turn.user_content[:40]
        enforce_limits(document)
        return StoredConversation.model_validate(document).model_dump(mode="json")

    def create_with_turn(self, current: StoredConversation, turn: TurnInput) -> dict:
        """An unsuccessful first GPT request never leaves an empty conversation."""
        with self._errors():
            if current.messages or current.revision != 0:
                raise ValueError("New conversation required")
            json.dumps(turn.assistant.plan, ensure_ascii=False, allow_nan=False)
            document = self._append_turn(current, turn)
            return self._response(self._stored(self.repository.create(document)))

    def save_turn(self, conversation_id: str, expected_revision: int, turn: TurnInput) -> dict:
        """A completed pair is committed in one write with optimistic concurrency."""
        with self._errors():
            if type(expected_revision) is not int or expected_revision < 0:
                raise ValueError("Expected revision must be a non-negative integer")
            # Validate before Pydantic JSON serialization can normalize NaN to null.
            json.dumps(turn.assistant.plan, ensure_ascii=False, allow_nan=False)
            current = self._stored(self.repository.get(conversation_id))
            if current.revision != expected_revision:
                raise ConversationConflict()
            document = self._append_turn(current, turn)
            saved = self.repository.save_turn(conversation_id, document, expected_revision)
            return self._response(self._stored(saved))

    def delete(self, conversation_id: str) -> None:
        with self._errors():
            self.repository.delete(conversation_id)
