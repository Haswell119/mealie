import shutil
from collections.abc import Callable
from pathlib import Path

from pydantic import UUID4

from mealie.core.config import get_app_dirs
from mealie.repos.all_repositories import get_repositories
from mealie.repos.repository_factory import AllRepositories
from mealie.schema.personal.enums import InspirationStatus
from mealie.schema.personal.inspiration import (
    InspirationCreate,
    InspirationDraft,
    InspirationOut,
    InspirationSave,
    InspirationUpdate,
)
from mealie.schema.recipe.recipe import RecipeDraft
from mealie.schema.recipe.recipe_ingredient import RecipeIngredient
from mealie.schema.recipe.recipe_step import RecipeStep
from mealie.services.recipe.recipe_service import RecipeService

from .errors import PersonalError, PersonalNotFound

ALLOWED_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


class InspirationService:
    """
    Cooking ideas, from the first note to a validated recipe.

    An inspiration becomes a draft, and a draft becomes a native recipe only when the user validates it.
    """

    def __init__(self, repos: AllRepositories, recipe_service: Callable[[], RecipeService] | None = None) -> None:
        self.repos = repos
        self.inspirations = repos.pe_inspirations
        self._recipe_service = recipe_service

    @property
    def _scope(self) -> dict:
        return {"group_id": self.repos.group_id, "household_id": self.repos.household_id}

    def with_recipe_slug(self, inspiration: InspirationOut) -> InspirationOut:
        """Add the slug of the recipe that a validated inspiration became, so that a client can link to it."""
        if inspiration.recipe_id is not None:
            recipes = get_repositories(self.repos.session, group_id=self.repos.group_id, household_id=None).recipes
            recipe = recipes.get_one(inspiration.recipe_id, "id")
            inspiration.recipe_slug = recipe.slug if recipe else None
        return inspiration

    def get_one(self, inspiration_id: UUID4) -> InspirationOut:
        inspiration = self.inspirations.get_one(inspiration_id)
        if inspiration is None:
            raise PersonalNotFound("Inspiration not found.")
        return self.with_recipe_slug(inspiration)

    def create(self, data: InspirationCreate) -> InspirationOut:
        self._check(data)
        return self.inspirations.create(data.cast(InspirationSave, **self._scope))

    def update(self, inspiration_id: UUID4, data: InspirationUpdate) -> InspirationOut:
        existing = self.get_one(inspiration_id)
        self._check(data)
        if existing.status == InspirationStatus.VALIDATED:
            raise PersonalError("INSPIRATION_VALIDATED", "A validated inspiration is a recipe now. Edit the recipe.")

        values = data.model_dump(exclude={"draft"})
        if data.draft is not None:
            values["draft"] = data.draft.model_dump()
            values["status"] = InspirationStatus.DRAFT
        return self.with_recipe_slug(self.inspirations.update(inspiration_id, values))

    def delete(self, inspiration_id: UUID4) -> InspirationOut:
        inspiration = self.get_one(inspiration_id)
        self.inspirations.delete(inspiration_id)
        shutil.rmtree(self._directory(inspiration_id), ignore_errors=True)
        return inspiration

    @staticmethod
    def _check(data: InspirationCreate) -> None:
        if not data.title.strip():
            raise PersonalError("INSPIRATION_TITLE_REQUIRED", "An inspiration needs a title.")

    # ================================================================
    # Workflow

    def start_draft(self, inspiration_id: UUID4) -> InspirationOut:
        """Turn an inspiration into an empty draft that the user fills in."""
        inspiration = self.get_one(inspiration_id)
        if inspiration.status == InspirationStatus.VALIDATED:
            raise PersonalError("INSPIRATION_VALIDATED", "This inspiration is already a recipe.")
        draft = inspiration.draft or InspirationDraft(name=inspiration.title, notes=inspiration.text)
        return self.set_draft(inspiration_id, draft)

    def set_draft(self, inspiration_id: UUID4, draft: InspirationDraft) -> InspirationOut:
        return self.with_recipe_slug(
            self.inspirations.update(inspiration_id, {"draft": draft.model_dump(), "status": InspirationStatus.DRAFT})
        )

    def validate(self, inspiration_id: UUID4) -> InspirationOut:
        """
        Create the native recipe of a draft. The user does this, never the assistant.

        The draft needs a name, a number of servings and at least one ingredient: without servings, the
        application cannot scale the recipe to a number of persons.
        """
        inspiration = self.get_one(inspiration_id)
        if inspiration.status == InspirationStatus.VALIDATED:
            raise PersonalError("INSPIRATION_VALIDATED", "This inspiration is already a recipe.")
        draft = inspiration.draft
        if draft is None:
            raise PersonalError("DRAFT_MISSING", "Write the draft of the recipe first.")

        ingredients = [line.strip() for line in draft.ingredients if line.strip()]
        instructions = [line.strip() for line in draft.instructions if line.strip()]
        if not draft.name.strip():
            raise PersonalError("DRAFT_NAME_REQUIRED", "The recipe needs a name.")
        if draft.recipe_servings <= 0:
            raise PersonalError("DRAFT_SERVINGS_REQUIRED", "Set the number of servings of the recipe.")
        if not ingredients:
            raise PersonalError("DRAFT_INGREDIENTS_REQUIRED", "The recipe needs at least one ingredient.")
        if self._recipe_service is None:
            raise PersonalError("RECIPE_SERVICE_MISSING", "The recipe cannot be created here.")

        recipe = self._recipe_service().create_one(
            RecipeDraft(
                name=draft.name.strip(),
                description=draft.description or "",
                recipe_servings=draft.recipe_servings,
                org_url=inspiration.url,
                recipe_ingredient=[RecipeIngredient(note=line) for line in ingredients],
                recipe_instructions=[RecipeStep(text=line) for line in instructions],
            )
        )
        updated = self.inspirations.update(
            inspiration_id, {"status": InspirationStatus.VALIDATED, "recipe_id": recipe.id}
        )
        return self.with_recipe_slug(updated)

    # ================================================================
    # Image

    @staticmethod
    def _directory(inspiration_id: UUID4) -> Path:
        return get_app_dirs().DATA_DIR / "inspirations" / str(inspiration_id)

    def set_image(self, inspiration_id: UUID4, content_type: str | None, content: bytes) -> InspirationOut:
        self.get_one(inspiration_id)
        extension = ALLOWED_IMAGE_TYPES.get(content_type or "")
        if extension is None:
            raise PersonalError("IMAGE_TYPE_NOT_ALLOWED", "Use a JPEG, PNG or WebP image.")
        if len(content) > MAX_IMAGE_BYTES:
            raise PersonalError("IMAGE_TOO_LARGE", "The image is larger than 10 MB.")
        if not content:
            raise PersonalError("IMAGE_EMPTY", "The image is empty.")

        directory = self._directory(inspiration_id)
        shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"image.{extension}"
        (directory / filename).write_bytes(content)
        return self.with_recipe_slug(self.inspirations.update(inspiration_id, {"image": filename}))

    def image_path(self, inspiration_id: UUID4) -> Path:
        inspiration = self.get_one(inspiration_id)
        if not inspiration.image or inspiration.image not in {f"image.{ext}" for ext in ALLOWED_IMAGE_TYPES.values()}:
            raise PersonalNotFound("This inspiration has no image.")
        path = self._directory(inspiration_id) / inspiration.image
        if not path.is_file():
            raise PersonalNotFound("This inspiration has no image.")
        return path
