"""Conversation persistence contract and application-owned failure types."""
from typing import Protocol


class ConversationNotFound(Exception):
    pass


class ConversationConflict(Exception):
    pass


class ConversationLimitExceeded(Exception):
    pass


class ConversationTooLarge(Exception):
    pass


class ConversationRepository(Protocol):
    def create(self, document: dict) -> dict: ...

    def list_all(self) -> list[dict]: ...

    def get(self, conversation_id: str) -> dict: ...

    def save_turn(self, conversation_id: str, document: dict, expected_revision: int) -> dict: ...

    def delete(self, conversation_id: str) -> None: ...
