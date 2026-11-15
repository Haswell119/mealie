import json
from pathlib import Path
from typing import Any

from pydantic import UUID4

from mealie.core.root_logger import get_logger
from mealie.repos.repository_factory import AllRepositories
from mealie.schema.personal.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantStatus,
    AssistantToolCall,
)
from mealie.schema.personal.inspiration import InspirationDraft
from mealie.services.openai import OpenAIService
from mealie.services.openai.openai import OpenAINotEnabledException

from .assistant_privacy import Anonymizer
from .assistant_tools import TOOL_DEFINITIONS, AssistantTools

logger = get_logger()

MAX_ROUNDS = 6
MAX_HISTORY = 12
MAX_TIMEOUT_SECONDS = 90

_DATA_DIR = Path(__file__).parent / "data"
SYSTEM_PROMPT = (_DATA_DIR / "assistant_system_prompt.txt").read_text(encoding="utf-8").strip()
STRUCTURE_PROMPT = (_DATA_DIR / "assistant_structure_prompt.txt").read_text(encoding="utf-8").strip()


class AssistantService:
    """
    The conversation with the AI provider.

    Every failure of the provider becomes a normal answer with `available=False`. No other part of the
    application depends on this service.
    """

    def __init__(self, repos: AllRepositories, user_id: UUID4) -> None:
        self.repos = repos
        self.user_id = user_id

    def _openai(self) -> OpenAIService:
        return OpenAIService(self.repos)

    def status(self) -> AssistantStatus:
        try:
            provider = self._openai()._get_provider()
        except Exception:
            return AssistantStatus(enabled=False)
        return AssistantStatus(enabled=True, provider_name=provider.name, model=provider.model)

    def _anonymizer(self) -> Anonymizer:
        return Anonymizer({person.id: person.display_name for person in self.repos.pe_persons.get_all()})

    @staticmethod
    def _unavailable(error: str, **extra) -> AssistantChatResponse:
        return AssistantChatResponse(available=False, error=error, **extra)

    async def chat(self, request: AssistantChatRequest) -> AssistantChatResponse:  # noqa: C901
        import openai

        try:
            service = self._openai()
            provider = service._get_provider()
            client = service.get_client(provider)
        except OpenAINotEnabledException:
            return self._unavailable("NOT_CONFIGURED")
        except Exception as e:
            logger.warning(f"Assistant could not start: {e.__class__.__name__}")
            return self._unavailable("PROVIDER_ERROR")

        anonymizer = self._anonymizer()
        tools = AssistantTools(self.repos, self.user_id, anonymizer)
        timeout = min(provider.timeout or MAX_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS)

        system = SYSTEM_PROMPT
        if request.event_id is not None:
            system += f"\n\nL'utilisateur parle de l'événement dont l'identifiant est {request.event_id}."

        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for entry in request.history[-MAX_HISTORY:]:
            messages.append({"role": entry.role, "content": anonymizer.scrub(entry.content)})
        messages.append({"role": "user", "content": anonymizer.scrub(request.message)})

        executed: list[AssistantToolCall] = []
        use_tools = True

        for _ in range(MAX_ROUNDS):
            kwargs: dict[str, Any] = {"model": provider.model, "messages": messages, "timeout": timeout}
            if use_tools:
                kwargs["tools"] = TOOL_DEFINITIONS
            try:
                completion = await client.chat.completions.create(**kwargs)
            except openai.BadRequestError:
                if not use_tools:
                    return self._unavailable("PROVIDER_ERROR", tool_calls=executed, proposals=tools.proposals)
                # The model does not support functions: go on as a plain conversation.
                use_tools = False
                continue
            except Exception as e:
                logger.warning(f"Assistant request failed: {e.__class__.__name__}")
                return self._unavailable("PROVIDER_ERROR", tool_calls=executed, proposals=tools.proposals)

            try:
                message = completion.choices[0].message
            except AttributeError, IndexError, TypeError:
                return self._unavailable("PROVIDER_ERROR", tool_calls=executed, proposals=tools.proposals)

            calls = getattr(message, "tool_calls", None) or []
            if not (use_tools and calls):
                reply = anonymizer.restore(getattr(message, "content", None) or "")
                return AssistantChatResponse(reply=reply, tool_calls=executed, proposals=tools.proposals)

            messages.append(
                {
                    "role": "assistant",
                    "content": getattr(message, "content", None) or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.function.name, "arguments": call.function.arguments or "{}"},
                        }
                        for call in calls
                    ],
                }
            )
            for call in calls:
                try:
                    arguments = json.loads(call.function.arguments or "{}")
                    if not isinstance(arguments, dict):
                        arguments = {}
                except TypeError, ValueError:
                    arguments = {}

                result = tools.execute(call.function.name, arguments)
                executed.append(AssistantToolCall(name=call.function.name, arguments=arguments))
                # Tool results pass through the same filter as every other text that goes out.
                content = anonymizer.scrub(json.dumps(result, ensure_ascii=False, default=str))
                messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

        return AssistantChatResponse(reply="", error="TOO_MANY_STEPS", tool_calls=executed, proposals=tools.proposals)

    async def structure_note(self, title: str, text: str) -> InspirationDraft | None:
        """Ask the provider to turn a note into a draft of a recipe. Return None when the provider fails."""
        try:
            service = self._openai()
            provider = service._get_provider()
            client = service.get_client(provider)
            anonymizer = self._anonymizer()
            completion = await client.chat.completions.create(
                model=provider.model,
                timeout=min(provider.timeout or MAX_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS),
                messages=[
                    {"role": "system", "content": STRUCTURE_PROMPT},
                    {"role": "user", "content": anonymizer.scrub(f"Titre : {title}\n\n{text}")},
                ],
            )
            raw = completion.choices[0].message.content or ""
            start, end = raw.find("{"), raw.rfind("}")
            if start < 0 or end <= start:
                return None
            return InspirationDraft.model_validate(json.loads(raw[start : end + 1]))
        except Exception as e:
            logger.warning(f"Assistant could not structure a note: {e.__class__.__name__}")
            return None
