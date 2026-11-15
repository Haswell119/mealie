"""Assign each person to a variant of a dish and count the portions of each variant."""

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from mealie.schema.personal.enums import Appetite

from .units import to_decimal

APPETITE_FACTORS: dict[Appetite, Decimal] = {
    Appetite.SMALL: Decimal("0.75"),
    Appetite.NORMAL: Decimal("1"),
    Appetite.LARGE: Decimal("1.25"),
}


class MissingServingsError(ValueError):
    """A recipe has no number of servings, so its ingredients cannot be scaled to a number of portions."""

    def __init__(self, recipe_id: UUID | None, recipe_name: str | None) -> None:
        self.recipe_id = recipe_id
        self.recipe_name = recipe_name
        super().__init__(f"Recipe '{recipe_name}' has no servings")


@dataclass(frozen=True)
class Diner:
    person_id: UUID
    appetite: Appetite = Appetite.NORMAL

    @property
    def factor(self) -> Decimal:
        return APPETITE_FACTORS[self.appetite]


@dataclass(frozen=True)
class VariantOption:
    """A variant of a dish, with the restrictions that its recipe breaks."""

    variant_id: UUID
    incompatible_keys: frozenset[str] = frozenset()


@dataclass
class Assignment:
    by_person: dict[UUID, UUID] = field(default_factory=dict)
    unassigned: list[UUID] = field(default_factory=list)
    conflicts: dict[UUID, set[str]] = field(default_factory=dict)


def assign_variants(
    diners: list[Diner],
    individual_keys: dict[UUID, set[str]],
    variants: list[VariantOption],
    manual: dict[UUID, UUID] | None = None,
) -> Assignment:
    """
    Give each person the first variant that breaks none of the restrictions of that person.

    A manual choice is kept as it is. When it breaks a restriction of the person, the conflict is reported.
    A person without any compatible variant stays unassigned.
    """
    manual = manual or {}
    by_id = {variant.variant_id: variant for variant in variants}
    result = Assignment()

    for diner in diners:
        keys = individual_keys.get(diner.person_id, set())

        chosen = manual.get(diner.person_id)
        if chosen is not None and chosen in by_id:
            result.by_person[diner.person_id] = chosen
            broken = keys & by_id[chosen].incompatible_keys
            if broken:
                result.conflicts[diner.person_id] = set(broken)
            continue

        for variant in variants:
            if not (keys & variant.incompatible_keys):
                result.by_person[diner.person_id] = variant.variant_id
                break
        else:
            result.unassigned.append(diner.person_id)

    return result


def portions_by_variant(
    diners: list[Diner],
    assignment: Assignment,
    variants: list[VariantOption],
    leftover_portions: Decimal | float = 0,
    overrides: dict[UUID, Decimal | float] | None = None,
) -> dict[UUID, Decimal]:
    """
    Count the portions of each variant: the sum of the appetite factors of its persons.

    Leftover portions go to the first variant that has persons. An override replaces the count of its variant.
    """
    overrides = overrides or {}
    portions: dict[UUID, Decimal] = {variant.variant_id: Decimal("0") for variant in variants}

    for diner in diners:
        variant_id = assignment.by_person.get(diner.person_id)
        if variant_id is not None:
            portions[variant_id] += diner.factor

    leftovers = to_decimal(leftover_portions)
    if leftovers > 0 and variants:
        target = next((v.variant_id for v in variants if portions[v.variant_id] > 0), variants[0].variant_id)
        portions[target] += leftovers

    for variant_id, value in overrides.items():
        if variant_id in portions and value is not None:
            portions[variant_id] = to_decimal(value)

    return portions


def scale_for(
    portions: Decimal, servings: float | Decimal | None, recipe_id: UUID | None = None, recipe_name: str | None = None
) -> Decimal:
    """The factor that scales a recipe to a number of portions. A recipe without servings is an error."""
    recipe_servings = to_decimal(servings)
    if recipe_servings <= 0:
        raise MissingServingsError(recipe_id, recipe_name)
    return portions / recipe_servings
