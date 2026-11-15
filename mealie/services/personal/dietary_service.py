from datetime import UTC, datetime

from pydantic import UUID4

from mealie.repos.repository_factory import AllRepositories
from mealie.schema.personal.dietary import (
    DietaryRestrictionCreate,
    DietaryRestrictionOut,
    DietaryRestrictionSave,
    FoodComplianceOut,
    FoodRestrictionEffective,
    FoodRestrictionStatusOut,
    FoodRestrictionStatusSave,
    FoodRestrictionStatusUpdate,
    ToolRestrictionStatusCreate,
    ToolRestrictionStatusOut,
    ToolRestrictionStatusSave,
)
from mealie.schema.personal.enums import FindingCode, RestrictionKind, VerificationSource, VerificationStatus

from .engine.compliance import StatusBook, StoredStatus
from .engine.rules import classify_text
from .errors import PersonalError, PersonalNotFound

DEFAULT_RESTRICTIONS: list[tuple[str, str, RestrictionKind]] = [
    ("gluten", "Gluten", RestrictionKind.MEDICAL),
    ("meat", "Viande", RestrictionKind.ETHICAL),
    ("fish", "Poisson", RestrictionKind.ETHICAL),
    ("shellfish", "Crustacés et mollusques", RestrictionKind.ALLERGY),
    ("dairy", "Produits laitiers", RestrictionKind.ALLERGY),
    ("lactose", "Lactose", RestrictionKind.INTOLERANCE),
    ("egg", "Œufs", RestrictionKind.ALLERGY),
    ("peanut", "Arachides", RestrictionKind.ALLERGY),
    ("tree_nut", "Fruits à coque", RestrictionKind.ALLERGY),
    ("soy", "Soja", RestrictionKind.ALLERGY),
    ("pork", "Porc", RestrictionKind.ETHICAL),
    ("alcohol", "Alcool", RestrictionKind.PREFERENCE),
]


class DietaryService:
    """The catalog of dietary restrictions and the verification state of foods and tools."""

    def __init__(self, repos: AllRepositories) -> None:
        self.repos = repos
        self.restrictions_repo = repos.pe_dietary_restrictions
        self.food_status_repo = repos.pe_food_restriction_status
        self.tool_status_repo = repos.pe_tool_restriction_status

    @property
    def group_id(self) -> UUID4:
        return self.repos.group_id  # type: ignore[return-value]

    # ================================================================
    # Catalog

    def ensure_defaults(self) -> list[DietaryRestrictionOut]:
        """Return the restrictions of the group. Create the standard ones the first time."""
        existing = self.restrictions_repo.get_all(order_by="name", order_descending=False)
        existing_keys = {restriction.key for restriction in existing}
        if any(restriction.is_system for restriction in existing):
            return existing

        missing = [
            DietaryRestrictionSave(group_id=self.group_id, key=key, name=name, kind=kind, is_system=True)
            for key, name, kind in DEFAULT_RESTRICTIONS
            if key not in existing_keys
        ]
        if missing:
            self.restrictions_repo.create_many(missing)
        return self.restrictions_repo.get_all(order_by="name", order_descending=False)

    def create_restriction(self, data: DietaryRestrictionCreate) -> DietaryRestrictionOut:
        self.ensure_defaults()
        if self.restrictions_repo.get_one(data.key, "key") is not None:
            raise PersonalError("RESTRICTION_EXISTS", f"A restriction with the key '{data.key}' already exists.")
        return self.restrictions_repo.create(data.cast(DietaryRestrictionSave, group_id=self.group_id))

    def update_restriction(self, restriction_id: UUID4, data: DietaryRestrictionCreate) -> DietaryRestrictionOut:
        restriction = self.get_restriction(restriction_id)
        # The key of a standard restriction selects its keyword rules, so it does not change.
        key = restriction.key if restriction.is_system else data.key
        return self.restrictions_repo.update(
            restriction_id, {"key": key, "name": data.name, "kind": data.kind, "description": data.description}
        )

    def delete_restriction(self, restriction_id: UUID4) -> DietaryRestrictionOut:
        restriction = self.get_restriction(restriction_id)
        if restriction.is_system:
            raise PersonalError("RESTRICTION_IS_STANDARD", "A standard restriction cannot be deleted.")
        if self.repos.pe_person_restrictions.multi_query({"restriction_id": restriction_id}, limit=1):
            raise PersonalError("RESTRICTION_IN_USE", "A person still has this restriction.")

        for status in self.food_status_repo.multi_query({"restriction_id": restriction_id}):
            self.food_status_repo.delete(status.id)
        for tool_status in self.tool_status_repo.multi_query({"restriction_id": restriction_id}):
            self.tool_status_repo.delete(tool_status.id)
        return self.restrictions_repo.delete(restriction_id)

    def get_restriction(self, restriction_id: UUID4) -> DietaryRestrictionOut:
        restriction = self.restrictions_repo.get_one(restriction_id)
        if restriction is None:
            raise PersonalNotFound("Restriction not found.")
        return restriction

    def restrictions_by_id(self) -> dict[UUID4, DietaryRestrictionOut]:
        return {restriction.id: restriction for restriction in self.ensure_defaults()}

    def restrictions_by_key(self) -> dict[str, DietaryRestrictionOut]:
        return {restriction.key: restriction for restriction in self.ensure_defaults()}

    # ================================================================
    # Food status

    def _require_food(self, food_id: UUID4):
        food = self.repos.ingredient_foods.get_one(food_id)
        if food is None:
            raise PersonalNotFound("Food not found.")
        return food

    def set_food_status(
        self, food_id: UUID4, restriction_id: UUID4, data: FoodRestrictionStatusUpdate, user_id: UUID4
    ) -> FoodRestrictionStatusOut:
        """Store the state that a person chose for a food. This is the only way to mark a food as verified."""
        self._require_food(food_id)
        self.get_restriction(restriction_id)

        save = FoodRestrictionStatusSave(
            group_id=self.group_id,
            food_id=food_id,
            restriction_id=restriction_id,
            status=data.status,
            source=VerificationSource.MANUAL,
            reason=data.reason,
            verified_by=user_id,
            verified_at=datetime.now(UTC),
        )
        return self._upsert_food_status(save)

    def suggest_food_status(
        self,
        food_id: UUID4,
        restriction_id: UUID4,
        status: VerificationStatus,
        source: VerificationSource,
        reason: str | None = None,
    ) -> FoodRestrictionStatusOut | None:
        """
        Store a state that does not come from a person: a rule, a product label or the assistant.

        Such a source can never mark a food as verified, and never replaces the choice of a person.
        """
        if source == VerificationSource.MANUAL:
            raise PersonalError("SOURCE_NOT_ALLOWED", "A suggestion cannot use the manual source.")
        if status == VerificationStatus.VERIFIED:
            status = VerificationStatus.UNVERIFIED

        existing = self._find_food_status(food_id, restriction_id)
        if existing is not None and existing.source == VerificationSource.MANUAL:
            return None

        save = FoodRestrictionStatusSave(
            group_id=self.group_id,
            food_id=food_id,
            restriction_id=restriction_id,
            status=status,
            source=source,
            reason=reason,
        )
        return self._upsert_food_status(save)

    def clear_food_status(self, food_id: UUID4, restriction_id: UUID4) -> None:
        existing = self._find_food_status(food_id, restriction_id)
        if existing is not None:
            self.food_status_repo.delete(existing.id)

    def _find_food_status(self, food_id: UUID4, restriction_id: UUID4) -> FoodRestrictionStatusOut | None:
        found = self.food_status_repo.multi_query({"food_id": food_id, "restriction_id": restriction_id}, limit=1)
        return found[0] if found else None

    def _upsert_food_status(self, save: FoodRestrictionStatusSave) -> FoodRestrictionStatusOut:
        existing = self._find_food_status(save.food_id, save.restriction_id)
        if existing is None:
            return self.food_status_repo.create(save)
        return self.food_status_repo.update(existing.id, save)

    def food_statuses(self, food_id: UUID4) -> list[FoodRestrictionStatusOut]:
        return self.food_status_repo.multi_query({"food_id": food_id})

    def food_compliance(self, food_id: UUID4) -> FoodComplianceOut:
        """The state that the application uses for one food, for every restriction of the group."""
        food = self._require_food(food_id)
        stored = {status.restriction_id: status for status in self.food_statuses(food_id)}

        statuses: list[FoodRestrictionEffective] = []
        for restriction in self.ensure_defaults():
            common = {
                "restriction_id": restriction.id,
                "restriction_key": restriction.key,
                "restriction_name": restriction.name,
            }
            row = stored.get(restriction.id)
            if row is not None:
                statuses.append(
                    FoodRestrictionEffective(
                        status=row.status,
                        code=FindingCode.STORED,
                        reason=row.reason,
                        source=row.source,
                        stored=True,
                        **common,
                    )
                )
                continue

            rule = classify_text(food.name, restriction.key)
            if rule is not None:
                statuses.append(
                    FoodRestrictionEffective(
                        status=rule.status, code=rule.code, term=rule.term, source=VerificationSource.RULE, **common
                    )
                )
            else:
                statuses.append(
                    FoodRestrictionEffective(status=VerificationStatus.UNVERIFIED, code=FindingCode.NO_DATA, **common)
                )

        return FoodComplianceOut(food_id=food.id, food_name=food.name, statuses=statuses)

    # ================================================================
    # Tool status

    def flag_tool(self, data: ToolRestrictionStatusCreate) -> ToolRestrictionStatusOut:
        if self.repos.tools.get_one(data.tool_id, "id") is None:
            raise PersonalNotFound("Tool not found.")
        self.get_restriction(data.restriction_id)

        existing = self.tool_status_repo.multi_query(
            {"tool_id": data.tool_id, "restriction_id": data.restriction_id}, limit=1
        )
        save = data.cast(ToolRestrictionStatusSave, group_id=self.group_id)
        if existing:
            return self.tool_status_repo.update(existing[0].id, save)
        return self.tool_status_repo.create(save)

    def unflag_tool(self, status_id: UUID4) -> ToolRestrictionStatusOut:
        if self.tool_status_repo.get_one(status_id) is None:
            raise PersonalNotFound("Tool flag not found.")
        return self.tool_status_repo.delete(status_id)

    def tool_flags(self) -> list[ToolRestrictionStatusOut]:
        return self.tool_status_repo.get_all()

    # ================================================================
    # Engine input

    def status_book(self) -> StatusBook:
        """Everything the user stored about foods and tools, in the form the compliance engine reads."""
        keys = {restriction.id: restriction.key for restriction in self.ensure_defaults()}
        book = StatusBook()
        for status in self.food_status_repo.get_all():
            key = keys.get(status.restriction_id)
            if key is not None:
                book.foods[(status.food_id, key)] = StoredStatus(status.status, status.source, status.reason)
        for tool_status in self.tool_status_repo.get_all():
            key = keys.get(tool_status.restriction_id)
            if key is not None and tool_status.requires_check:
                book.tools[(tool_status.tool_id, key)] = tool_status.reason
        return book
