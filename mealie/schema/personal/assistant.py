from datetime import datetime
from typing import Any

from pydantic import UUID4, ConfigDict, Field

from mealie.schema._mealie import MealieModel
from mealie.schema._mealie.mealie_model import MealieOutModel
from mealie.schema.response.pagination import PaginationBase

from .enums import AiProposalKind, AiProposalStatus


class AssistantMessage(MealieModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class AssistantChatRequest(MealieModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[AssistantMessage] = []
    event_id: UUID4 | None = None
    """The meal event the conversation is about. The assistant then sees its anonymous constraints."""


class AssistantToolCall(MealieOutModel):
    name: str
    arguments: dict[str, Any] = {}


class AiProposalSave(MealieModel):
    group_id: UUID4
    household_id: UUID4
    kind: AiProposalKind
    status: AiProposalStatus = AiProposalStatus.PENDING
    title: str
    payload: dict | None = None
    event_id: UUID4 | None = None
    created_by: UUID4 | None = None
    decided_at: datetime | None = None
    result: dict | None = None


class AiProposalOut(MealieOutModel):
    id: UUID4
    kind: AiProposalKind
    status: AiProposalStatus = AiProposalStatus.PENDING
    title: str
    payload: dict[str, Any] | None = None
    event_id: UUID4 | None = None
    created_at: datetime | None = None
    decided_at: datetime | None = None
    result: dict[str, Any] | None = None
    model_config = ConfigDict(from_attributes=True)


class AiProposalPagination(PaginationBase):
    items: list[AiProposalOut]


class AssistantChatResponse(MealieOutModel):
    available: bool = True
    """False when no AI provider answers. Every other part of the application keeps working."""
    reply: str = ""
    tool_calls: list[AssistantToolCall] = []
    proposals: list[AiProposalOut] = []
    error: str | None = None


class AssistantStatus(MealieOutModel):
    enabled: bool = False
    provider_name: str | None = None
    model: str | None = None
