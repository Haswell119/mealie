from datetime import UTC, datetime

from pydantic import UUID4

from mealie.repos.repository_factory import AllRepositories
from mealie.schema.personal.person import (
    PersonCreate,
    PersonFoodPreferenceSave,
    PersonOut,
    PersonRestrictionSave,
    PersonSave,
)

from .dietary_service import DietaryService
from .errors import PersonalError, PersonalNotFound


class PersonService:
    """The persons the household cooks for, with their restrictions and preferences."""

    def __init__(self, repos: AllRepositories) -> None:
        self.repos = repos
        self.persons = repos.pe_persons
        self.dietary = DietaryService(repos)

    def get_one(self, person_id: UUID4) -> PersonOut:
        person = self.persons.get_one(person_id)
        if person is None:
            raise PersonalNotFound("Person not found.")
        return person

    def create(self, data: PersonCreate, user_id: UUID4) -> PersonOut:
        self._check(data)
        person = self.persons.create(self._to_save(data, user_id, None))
        self._replace_children(person.id, data)
        return self.get_one(person.id)

    def update(self, person_id: UUID4, data: PersonCreate, user_id: UUID4) -> PersonOut:
        existing = self.get_one(person_id)
        self._check(data)
        self.persons.update(person_id, self._to_save(data, user_id, existing))
        self._replace_children(person_id, data)
        return self.get_one(person_id)

    def delete(self, person_id: UUID4) -> PersonOut:
        """Delete a person and every record about that person, including the place in past events."""
        person = self.get_one(person_id)

        for repo in (
            self.repos.pe_meal_event_assignments,
            self.repos.pe_meal_event_overrides,
            self.repos.pe_meal_event_guests,
        ):
            for row in repo.multi_query({"person_id": person_id}):
                repo.delete(row.id)

        for event in self.repos.pe_meal_events.multi_query({"cook_person_id": person_id}):
            self.repos.pe_meal_events.update(event.id, {"cook_person_id": None})

        self.persons.delete(person_id)
        return person

    def _check(self, data: PersonCreate) -> None:
        if not data.display_name.strip():
            raise PersonalError("PERSON_NAME_REQUIRED", "A person needs a name.")

        holds_personal_data = bool(data.restrictions or data.food_preferences or (data.notes or "").strip())
        if holds_personal_data and not (data.consent_given or data.is_me):
            raise PersonalError(
                "CONSENT_REQUIRED",
                "Record the consent of the person before you store restrictions, preferences or notes.",
            )

        known = self.dietary.restrictions_by_id()
        seen: set[UUID4] = set()
        for restriction in data.restrictions:
            if restriction.restriction_id not in known:
                raise PersonalNotFound("Restriction not found.")
            if restriction.restriction_id in seen:
                raise PersonalError("RESTRICTION_DUPLICATE", "The same restriction is listed twice.")
            seen.add(restriction.restriction_id)

        seen_foods: set[UUID4] = set()
        for preference in data.food_preferences:
            if self.repos.ingredient_foods.get_one(preference.food_id) is None:
                raise PersonalNotFound("Food not found.")
            if preference.food_id in seen_foods:
                raise PersonalError("PREFERENCE_DUPLICATE", "The same food is listed twice.")
            seen_foods.add(preference.food_id)

    def _to_save(self, data: PersonCreate, user_id: UUID4, existing: PersonOut | None) -> PersonSave:
        consent_given_at = None
        if data.consent_given or data.is_me:
            consent_given_at = (existing.consent_given_at if existing else None) or datetime.now(UTC)

        return PersonSave(
            group_id=self.repos.group_id,  # type: ignore[arg-type]
            household_id=self.repos.household_id,  # type: ignore[arg-type]
            display_name=data.display_name.strip(),
            appetite=data.appetite,
            notes=data.notes,
            linked_user_id=user_id if data.is_me else None,
            consent_given_at=consent_given_at,
            consent_note=data.consent_note if consent_given_at else None,
        )

    def _replace_children(self, person_id: UUID4, data: PersonCreate) -> None:
        restrictions = self.repos.pe_person_restrictions
        preferences = self.repos.pe_person_food_preferences
        scope = {"group_id": self.repos.group_id, "household_id": self.repos.household_id, "person_id": person_id}

        for restriction_row in restrictions.multi_query({"person_id": person_id}):
            restrictions.delete(restriction_row.id)
        for preference_row in preferences.multi_query({"person_id": person_id}):
            preferences.delete(preference_row.id)

        if data.restrictions:
            restrictions.create_many([r.cast(PersonRestrictionSave, **scope) for r in data.restrictions])
        if data.food_preferences:
            preferences.create_many([p.cast(PersonFoodPreferenceSave, **scope) for p in data.food_preferences])
