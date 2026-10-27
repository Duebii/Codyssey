from __future__ import annotations

from app.core.firebase import FirebaseClientProvider
from app.core.openai_client import AIGateway, OpenAIGateway
from app.repositories.conversations import ConversationRepository
from app.repositories.firestore_conversations import FirestoreConversationRepository
from app.repositories.firestore_records import FirestoreRecordRepository
from app.repositories.records import RecordRepository
from app.services.records import RecordService
from app.services.summaries import SummaryService
from app.services.conversations import ConversationService
from app.services.chat import ChatService
from app.schemas.chat import ChatInput


class ManagerService:
    """Share lazy adapters and the same summary service across API and GPT."""

    def __init__(self, record_repository: RecordRepository | None = None,
                 conversation_repository: ConversationRepository | None = None, ai_gateway: AIGateway | None = None):
        provider = FirebaseClientProvider()
        repository = record_repository if record_repository is not None else FirestoreRecordRepository(client_provider=provider.get)
        conversation_repository = conversation_repository if conversation_repository is not None else FirestoreConversationRepository(client_provider=provider.get)
        self.summaries = SummaryService(repository)
        self.records = RecordService(repository, refresh_summary=self.summaries.get)
        self.conversations = ConversationService(conversation_repository)
        self.counsel = ChatService(self.summaries, self.conversations, ai_gateway if ai_gateway is not None else OpenAIGateway())

    def summary(self) -> dict:
        return self.summaries.get()

    def chat(self, payload: ChatInput, client: str) -> dict:
        return self.counsel.chat(payload, client)


def health() -> dict:
    return {"status": "ok", "service": "김실장", "stage": 7, "storage": "not_checked", "ai": "not_checked"}
