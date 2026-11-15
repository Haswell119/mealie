from datetime import datetime

from pydantic import UUID4, ConfigDict, model_validator

from mealie.schema._mealie import MealieModel
from mealie.schema._mealie.mealie_model import MealieOutModel
from mealie.schema.response.pagination import PaginationBase

from .enums import InspirationKind, InspirationStatus


class InspirationDraft(MealieModel):
    """A recipe that is not validated yet. Every quantity stays editable until the user validates it."""

    name: str = ""
    description: str | None = None
    recipe_servings: float = 0
    ingredients: list[str] = []
    instructions: list[str] = []
    notes: str | None = None


class InspirationCreate(MealieModel):
    title: str
    kind: InspirationKind = InspirationKind.IDEA
    url: str | None = None
    text: str | None = None
    tags: list[str] = []

    @model_validator(mode="after")
    def check_url(self):
        if self.url:
            lowered = self.url.strip().lower()
            if not (lowered.startswith("http://") or lowered.startswith("https://")):
                raise ValueError("url must use http or https")
        return self


class InspirationUpdate(InspirationCreate):
    draft: InspirationDraft | None = None


class InspirationSave(InspirationCreate):
    group_id: UUID4
    household_id: UUID4
    status: InspirationStatus = InspirationStatus.INSPIRATION
    draft: dict | None = None
    image: str | None = None
    recipe_id: UUID4 | None = None


class InspirationOut(MealieOutModel):
    id: UUID4
    group_id: UUID4
    household_id: UUID4
    title: str
    kind: InspirationKind
    url: str | None = None
    text: str | None = None
    image: str | None = None
    tags: list[str] = []
    status: InspirationStatus = InspirationStatus.INSPIRATION
    draft: InspirationDraft | None = None
    recipe_id: UUID4 | None = None
    recipe_slug: str | None = None
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def none_tags_to_empty(cls, data):
        if isinstance(data, dict) and data.get("tags") is None:
            data["tags"] = []
        return data


class InspirationPagination(PaginationBase):
    items: list[InspirationOut]
