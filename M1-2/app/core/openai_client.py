"""Lazy, bounded GPT adapters for OpenAI and the course gateway."""
from pathlib import Path
import json
import os
from threading import Lock
from typing import Literal, Mapping, Protocol

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from app.core.config import PROJECT_ROOT
from app.core.errors import ApiError
from app.schemas.plans import ModelReply


class InvalidModelReply(Exception):
    def __init__(self, reason="invalid_structure", field=None):
        self.reason = reason
        self.field = field
        super().__init__(reason)


class AIGateway(Protocol):
    def generate(self, messages: list[dict]) -> ModelReply: ...


class AISettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    api_key: SecretStr
    provider: Literal["openai", "codyssey"] = "openai"
    model: str = Field(default="gpt-6-luna", min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    max_output_tokens: int = Field(default=3000, ge=256, le=6000)
    timeout_seconds: float = Field(default=40, ge=5, le=60)
    reasoning_effort: str = Field(default="none", pattern=r"^(none|low|medium|omit)$")

    @property
    def base_url(self) -> str:
        # Explicit profiles prevent ambient/untrusted URL overrides receiving keys.
        return "https://copa.codyssey.kr/v1" if self.provider == "codyssey" else "https://api.openai.com/v1"


def load_ai_settings(env_file: Path | None = None, environ: Mapping[str, str] | None = None) -> AISettings:
    try:
        path = PROJECT_ROOT / ".env" if env_file is None else env_file
        values = dict(dotenv_values(path, interpolate=False, encoding="utf-8-sig")) if path.is_file() else {}
        values.update(os.environ if environ is None else environ)
        provider = values.get("AI_PROVIDER", "openai")
        key = (values.get("OPENAI_API_KEY") or "").strip()
        if not key:
            raise ApiError(503, "ai_unavailable", "AI API 키가 비어 있습니다. 백엔드 환경변수를 설정해 주세요. GPT를 호출하지 않았습니다.")
        return AISettings(api_key=key, provider=provider,
                          model=values.get("OPENAI_MODEL", "gpt-5-mini" if provider == "codyssey" else "gpt-6-luna"),
                          max_output_tokens=values.get("OPENAI_MAX_OUTPUT_TOKENS", "3000"),
                          timeout_seconds=values.get("OPENAI_TIMEOUT_SECONDS", "40"),
                          reasoning_effort=values.get("OPENAI_REASONING_EFFORT", "omit" if provider == "codyssey" else "none"))
    except ApiError:
        raise
    except Exception:
        raise ApiError(503, "ai_unavailable", "AI 제공자·모델·토큰·시간 제한 환경변수의 형식·범위를 확인해 주세요. GPT를 호출하지 않았습니다.") from None


class OpenAIGateway:
    def __init__(self, env_file: Path | None = None, environ: Mapping[str, str] | None = None, client_factory=None):
        self.env_file, self.environ = env_file, environ
        self.client_factory = client_factory
        self._client = None
        self._settings = None
        self._lock = Lock()

    def _connection(self):
        import openai

        with self._lock:
            if self._client is None:
                settings = load_ai_settings(self.env_file, self.environ)
                factory = self.client_factory or openai.OpenAI
                self._client = factory(api_key=settings.api_key.get_secret_value(), base_url=settings.base_url,
                                       timeout=settings.timeout_seconds, max_retries=0)
                self._settings = settings
            return self._client, self._settings

    def generate(self, messages: list[dict]) -> ModelReply:
        import openai

        try:
            client, settings = self._connection()
            reasoning = {} if settings.reasoning_effort == "omit" else {"effort": settings.reasoning_effort}
            if settings.provider == "codyssey":
                # Course gateway rejects response_format (JSON/strict-schema modes).
                # Its basic chat API works; request JSON in text, then validate locally.
                schema = json.dumps(ModelReply.model_json_schema(), ensure_ascii=False, separators=(",", ":"))
                instruction = {"role": "system", "content": "JSON_SCHEMA=" + schema +
                    "\n위 스키마에 맞는 JSON 객체 하나만 출력하세요. 마크다운 코드 블록이나 앞뒤 설명은 쓰지 마세요. 모든 최상위 필드와 context_update 네 필드를 포함하세요."}
                wire_messages = [*messages[:-1], instruction, *messages[-1:]]
                completion = client.chat.completions.create(model=settings.model, messages=wire_messages,
                    max_completion_tokens=settings.max_output_tokens)
                if not completion.choices:
                    raise InvalidModelReply()
                choice = completion.choices[0]
                if choice.message.refusal or choice.finish_reason == "content_filter":
                    raise ApiError(502, "ai_unavailable", "GPT가 이 질문에 응답을 제공하지 않았습니다. 질문과 답변을 저장하지 않았습니다. 질문을 바꿔 주세요.")
                if choice.finish_reason != "stop" or not choice.message.content:
                    raise InvalidModelReply("output_limit" if choice.finish_reason == "length" else "empty_output")
                return ModelReply.model_validate_json(choice.message.content)
            response = client.responses.parse(model=settings.model, input=messages, text_format=ModelReply,
                max_output_tokens=settings.max_output_tokens, reasoning=reasoning, store=False)
            if any(item.type == "message" and any(part.type == "refusal" for part in item.content) for item in response.output):
                raise ApiError(502, "ai_unavailable", "GPT가 이 질문에 응답을 제공하지 않았습니다. 질문과 답변을 저장하지 않았습니다. 질문을 바꿔 주세요.")
            if response.status != "completed" or response.output_parsed is None:
                raise InvalidModelReply()
            return response.output_parsed
        except ApiError:
            raise
        except InvalidModelReply:
            raise
        except (ValidationError, ValueError, openai.LengthFinishReasonError):
            raise InvalidModelReply("json_or_schema") from None
        except openai.APITimeoutError:
            raise ApiError(504, "upstream_timeout", "GPT 응답 시간이 초과됐습니다. 대화를 저장하지 않았습니다. 자동 재호출하지 않습니다.") from None
        except openai.AuthenticationError:
            raise ApiError(503, "ai_unavailable", "선택한 AI 제공자와 키·프로젝트 권한을 확인해 주세요. GPT 응답과 대화를 저장하지 않았습니다.") from None
        except openai.RateLimitError:
            raise ApiError(429, "rate_limited", "AI 제공자의 요청 한도 또는 사용 가능량을 확인해 주세요. 대화를 저장하지 않았습니다.") from None
        except openai.APIError:
            raise ApiError(502, "ai_unavailable", "GPT 요청을 완료하지 못했습니다. 모델·연결·서비스 상태를 확인해 주세요. 대화를 저장하지 않았습니다.") from None
        except Exception:
            raise ApiError(502, "ai_unavailable", "GPT 연결을 확인할 수 없습니다. 대화를 저장하지 않았습니다.") from None
