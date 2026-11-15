"""Resolve which dietary restrictions apply to a meal, and how far each one reaches."""

from dataclasses import dataclass, field
from uuid import UUID

from mealie.schema.personal.enums import RestrictionScope, RestrictionSeverity

ORIGIN_PERSON = "PERSON_DEFAULT"
ORIGIN_COOK = "COOK_PROFILE"
ORIGIN_EVENT = "EVENT_OVERRIDE"
ORIGIN_PREPARATION = "PREPARATION_OVERRIDE"


@dataclass(frozen=True)
class PersonRestriction:
    person_id: UUID
    restriction_key: str
    severity: RestrictionSeverity
    scope: RestrictionScope
    applies_when_cooking: bool = False


@dataclass(frozen=True)
class ScopeOverride:
    person_id: UUID
    restriction_key: str
    scope: RestrictionScope
    menu_item_id: UUID | None = None


@dataclass
class AppliedConstraint:
    restriction_key: str
    scope: RestrictionScope
    severity: RestrictionSeverity
    person_ids: list[UUID] = field(default_factory=list)
    origins: list[str] = field(default_factory=list)


@dataclass
class ConstraintSet:
    """
    The restrictions that apply to one preparation.

    `shared` applies to every portion. `individual` applies only to the portion of one person.
    """

    shared: dict[str, AppliedConstraint] = field(default_factory=dict)
    individual: dict[UUID, dict[str, AppliedConstraint]] = field(default_factory=dict)

    @property
    def shared_keys(self) -> set[str]:
        return set(self.shared)

    def individual_keys(self, person_id: UUID) -> set[str]:
        return set(self.individual.get(person_id, {}))

    def preparation_keys(self) -> set[str]:
        return {key for key, c in self.shared.items() if c.scope == RestrictionScope.ENTIRE_PREPARATION}


def _find_override(
    overrides: list[ScopeOverride], restriction: PersonRestriction, menu_item_id: UUID | None
) -> ScopeOverride | None:
    for override in overrides:
        if (override.person_id, override.restriction_key) != (restriction.person_id, restriction.restriction_key):
            continue
        if override.menu_item_id == menu_item_id:
            return override
    return None


def resolve_constraints(
    attending_ids: set[UUID],
    cook_id: UUID | None,
    restrictions: list[PersonRestriction],
    overrides: list[ScopeOverride] | None = None,
    menu_item_id: UUID | None = None,
) -> ConstraintSet:
    """
    Build the constraints of one preparation.

    The most specific source decides the scope of a restriction: an override on the preparation, then an
    override on the event, then the default of the person. Between persons, the widest scope wins.
    """
    overrides = overrides or []
    result = ConstraintSet()

    for restriction in restrictions:
        is_attending = restriction.person_id in attending_ids
        is_cooking = restriction.person_id == cook_id and restriction.applies_when_cooking
        if not (is_attending or is_cooking):
            continue

        scope = restriction.scope
        origin = ORIGIN_COOK if is_cooking else ORIGIN_PERSON

        event_override = _find_override(overrides, restriction, None)
        if event_override is not None:
            scope, origin = event_override.scope, ORIGIN_EVENT

        if menu_item_id is not None:
            preparation_override = _find_override(overrides, restriction, menu_item_id)
            if preparation_override is not None:
                scope, origin = preparation_override.scope, ORIGIN_PREPARATION

        if scope == RestrictionScope.INDIVIDUAL:
            if not is_attending:
                continue
            per_person = result.individual.setdefault(restriction.person_id, {})
            per_person[restriction.restriction_key] = AppliedConstraint(
                restriction.restriction_key, scope, restriction.severity, [restriction.person_id], [origin]
            )
            continue

        shared = result.shared.get(restriction.restriction_key)
        if shared is None:
            result.shared[restriction.restriction_key] = AppliedConstraint(
                restriction.restriction_key, scope, restriction.severity, [restriction.person_id], [origin]
            )
            continue

        if scope.rank > shared.scope.rank:
            shared.scope = scope
        if restriction.severity.rank > shared.severity.rank:
            shared.severity = restriction.severity
        shared.person_ids.append(restriction.person_id)
        shared.origins.append(origin)

    # A restriction that already applies to every portion needs no entry per person.
    for per_person in result.individual.values():
        for key in list(per_person):
            if key in result.shared:
                del per_person[key]
    result.individual = {person_id: keys for person_id, keys in result.individual.items() if keys}

    return result
