"""Latest summary -> bounded GPT request -> validation -> atomic saved turn."""
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

from pydantic import ValidationError

from app.core.errors import ApiError
from app.core.openai_client import AIGateway, InvalidModelReply
from app.schemas.chat import ChatInput
from app.schemas.conversations import AssistantDraft, ContextPatch, Evidence, TurnInput
from app.schemas.plans import ModelReply
from app.services.chat_limits import ChatGuard
from app.services.chat_prompt import build_messages, render_reply
from app.services.chat_validation import validate_reply, verified_context
from app.services.conversations import ConversationService
from app.services.summaries import SummaryService

logger = logging.getLogger("kim_manager.chat")

REPAIR = """직전 출력은 검증을 통과하지 못했습니다. 원래 사용자 입력과 조건만 다시 확인해 새 JSON을 반환하세요.
시간은 최신 조건과 같아야 하고 단계 합+완충은 그 이하여야 합니다. 모든 작업 ID를 정확히 한 번 배치하고 선행 순서를 지키세요.
context_update는 이번 message의 정확한 인용과 명시한 값만 사용하세요. 폼과 충돌·불명확한 값은 변경하지 말고 clarification으로 확인하세요.
plan이 불가능하면 추측 없이 확인 질문을 하세요. plan content는 비워두고 비계획 content는 채우세요."""


class ChatService:
    def __init__(self, summaries: SummaryService, conversations: ConversationService, gateway: AIGateway, guard: ChatGuard | None = None):
        self.summaries, self.conversations, self.gateway = summaries, conversations, gateway
        self.guard = guard if guard is not None else ChatGuard()

    def chat(self, payload: ChatInput, client: str) -> dict:
        with self.guard.request(client, payload.conversation_id):
            current = self.conversations.prepare_chat(payload.conversation_id, payload.message)
            values = current.context.model_dump(mode="json")
            if payload.context is not None:
                values.update(payload.context.model_dump(mode="json", exclude_unset=True))
            try:
                context = ContextPatch.model_validate(values)
            except ValidationError:
                raise ApiError(422, "invalid_request", "현재 작업 목록과 새 조건의 선행 관계를 함께 확인해 주세요.", ["context"]) from None
            mode = payload.mode or current.mode
            # Exactly the service used by GET /api/data/summary; no HTTP self-call.
            summary = self.summaries.get()
            today = datetime.now(ZoneInfo("Asia/Seoul")).date()
            messages = build_messages(summary, context.model_dump(mode="json"), mode, payload.message,
                [message.model_dump(mode="json") for message in current.messages],
                sorted(payload.context.model_fields_set) if payload.context else [], today.isoformat())
            for attempt in range(2):
                self.guard.charge_model_call()
                try:
                    raw = self.gateway.generate(messages)
                    reply = ModelReply.model_validate(raw)
                    try:
                        updated = verified_context(reply, context, payload.message, payload.context, today)
                    except InvalidModelReply as failure:
                        raise InvalidModelReply("context_grounding", field=failure.field) from None
                    try:
                        validate_reply(reply, updated)
                    except InvalidModelReply:
                        raise InvalidModelReply("plan_constraints") from None
                    break
                except (InvalidModelReply, ValidationError, ValueError, TypeError) as failure:
                    # Only fixed internal categories, never model text or validation details.
                    reason = getattr(failure, "reason", "json_or_schema")
                    safe_reason = reason if reason in {"invalid_structure", "output_limit", "empty_output", "json_or_schema", "context_grounding", "plan_constraints"} else "invalid_structure"
                    field = getattr(failure, "field", None)
                    safe_field = field if field in {"goal", "available_minutes", "tasks", "constraints"} else "none"
                    logger.warning("AI output validation failed (attempt=%s, reason=%s, field=%s)", attempt + 1, safe_reason, safe_field)
                    if attempt:
                        raise ApiError(502, "ai_response_invalid", "GPT 응답의 조건·계획을 확인할 수 없습니다. 질문과 답변을 저장하지 않았습니다. 조건을 확인한 뒤 다시 시도해 주세요.") from None
                    # One bounded content repair only. SDK/network errors are never retried.
                    hint = (f"\ncontext_update.{safe_field}의 변경 근거가 검증되지 않았습니다. 기존 조건을 되풀이하거나 바꾸려는 의도가 명시되지 않았으면 해당 필드를 null로 두세요. "
                            "이번 발언의 명시적 변경만 정확히 인용하세요. 폼과 실제로 충돌하면 그 필드를 변경하지 말고 확인 질문을 하세요.") if safe_field != "none" else ""
                    messages = [*messages[:-1], {"role": "system", "content": REPAIR + hint}, messages[-1]]
            evidence = Evidence(source=summary["summary"]["source"], period=summary["summary"]["period"],
                as_of=summary["summary"]["as_of"], count=summary["summary"]["count"], data_revision=summary["data_revision"])
            draft = AssistantDraft(content=render_reply(reply, updated.model_dump(mode="json"), summary),
                reply_type=reply.reply_type, plan=reply.plan.model_dump(mode="json") if reply.plan else None, evidence=evidence)
            turn = TurnInput(user_content=payload.message, assistant=draft, mode=mode, context=updated)
            if payload.conversation_id is None:
                result = self.conversations.create_with_turn(current, turn)
            else:
                result = self.conversations.save_turn(current.id, current.revision, turn)
            saved = result["conversation"]
            return {"conversation_id": saved["id"], "message": saved["messages"][-1], "context": saved["context"]}
