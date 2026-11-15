from decimal import Decimal
from uuid import uuid4

import pytest

from mealie.schema.personal.enums import Appetite, RestrictionScope, RestrictionSeverity
from mealie.services.personal.engine.constraints import (
    ORIGIN_COOK,
    ORIGIN_EVENT,
    ORIGIN_PREPARATION,
    PersonRestriction,
    ScopeOverride,
    resolve_constraints,
)
from mealie.services.personal.engine.portions import (
    Diner,
    MissingServingsError,
    VariantOption,
    assign_variants,
    portions_by_variant,
    scale_for,
)

STRICT = RestrictionSeverity.STRICT
INDIVIDUAL = RestrictionScope.INDIVIDUAL
MEAL = RestrictionScope.ENTIRE_MEAL
PREPARATION = RestrictionScope.ENTIRE_PREPARATION


def test_individual_restriction_applies_only_to_its_person():
    vegetarian = uuid4()
    other = uuid4()
    restrictions = [
        PersonRestriction(vegetarian, "meat", STRICT, INDIVIDUAL),
        PersonRestriction(vegetarian, "fish", STRICT, INDIVIDUAL),
    ]
    result = resolve_constraints({vegetarian, other}, None, restrictions)

    assert result.shared == {}
    assert result.individual_keys(vegetarian) == {"meat", "fish"}
    assert result.individual_keys(other) == set()


def test_meal_scope_applies_to_every_portion():
    person = uuid4()
    result = resolve_constraints({person, uuid4()}, None, [PersonRestriction(person, "pork", STRICT, MEAL)])

    assert result.shared_keys == {"pork"}
    assert result.shared["pork"].scope == MEAL
    assert result.preparation_keys() == set()
    assert result.individual == {}


def test_preparation_scope_applies_to_every_portion_and_to_the_preparation():
    person = uuid4()
    result = resolve_constraints({person}, None, [PersonRestriction(person, "gluten", STRICT, PREPARATION)])

    assert result.shared_keys == {"gluten"}
    assert result.preparation_keys() == {"gluten"}


def test_cook_profile_applies_when_the_cook_is_not_a_guest():
    cook = uuid4()
    guest = uuid4()
    restrictions = [PersonRestriction(cook, "gluten", STRICT, PREPARATION, applies_when_cooking=True)]

    result = resolve_constraints({guest}, cook, restrictions)
    assert result.shared["gluten"].origins == [ORIGIN_COOK]

    assert resolve_constraints({guest}, None, restrictions).shared == {}


def test_restriction_of_an_absent_person_does_not_apply():
    absent = uuid4()
    result = resolve_constraints({uuid4()}, None, [PersonRestriction(absent, "gluten", STRICT, PREPARATION)])
    assert result.shared == {}
    assert result.individual == {}


def test_widest_scope_wins_between_persons():
    first, second = uuid4(), uuid4()
    restrictions = [
        PersonRestriction(first, "gluten", RestrictionSeverity.MODERATE, INDIVIDUAL),
        PersonRestriction(second, "gluten", STRICT, PREPARATION),
    ]
    result = resolve_constraints({first, second}, None, restrictions)

    assert result.shared["gluten"].scope == PREPARATION
    assert result.shared["gluten"].severity == STRICT
    assert result.individual == {}


def test_event_override_changes_the_scope_for_the_event():
    person = uuid4()
    restrictions = [PersonRestriction(person, "gluten", STRICT, PREPARATION)]
    overrides = [ScopeOverride(person, "gluten", INDIVIDUAL)]

    result = resolve_constraints({person}, None, restrictions, overrides)
    assert result.shared == {}
    assert result.individual[person]["gluten"].origins == [ORIGIN_EVENT]


def test_preparation_override_wins_over_event_override_for_its_preparation_only():
    person = uuid4()
    dessert = uuid4()
    main = uuid4()
    restrictions = [PersonRestriction(person, "meat", STRICT, INDIVIDUAL)]
    overrides = [
        ScopeOverride(person, "meat", MEAL),
        ScopeOverride(person, "meat", PREPARATION, menu_item_id=dessert),
    ]

    for_dessert = resolve_constraints({person}, None, restrictions, overrides, menu_item_id=dessert)
    assert for_dessert.shared["meat"].scope == PREPARATION
    assert for_dessert.shared["meat"].origins == [ORIGIN_PREPARATION]

    for_main = resolve_constraints({person}, None, restrictions, overrides, menu_item_id=main)
    assert for_main.shared["meat"].scope == MEAL


def test_override_on_one_person_does_not_relax_the_restriction_of_another_person():
    relaxed, strict = uuid4(), uuid4()
    restrictions = [
        PersonRestriction(relaxed, "gluten", STRICT, PREPARATION),
        PersonRestriction(strict, "gluten", STRICT, PREPARATION),
    ]
    overrides = [ScopeOverride(relaxed, "gluten", INDIVIDUAL)]

    result = resolve_constraints({relaxed, strict}, None, restrictions, overrides)
    assert result.shared["gluten"].scope == PREPARATION
    assert result.shared["gluten"].person_ids == [strict]


def test_each_person_gets_the_first_compatible_variant():
    vegetarian, omnivore = uuid4(), uuid4()
    beef, veggie = uuid4(), uuid4()
    variants = [VariantOption(beef, frozenset({"meat"})), VariantOption(veggie)]

    result = assign_variants([Diner(vegetarian), Diner(omnivore)], {vegetarian: {"meat", "fish"}}, variants)
    assert result.by_person == {vegetarian: veggie, omnivore: beef}
    assert result.unassigned == []


def test_person_without_compatible_variant_stays_unassigned():
    vegetarian = uuid4()
    variants = [VariantOption(uuid4(), frozenset({"meat"}))]
    result = assign_variants([Diner(vegetarian)], {vegetarian: {"meat"}}, variants)
    assert result.unassigned == [vegetarian]
    assert result.by_person == {}


def test_manual_assignment_is_kept_and_its_conflict_is_reported():
    vegetarian = uuid4()
    beef, veggie = uuid4(), uuid4()
    variants = [VariantOption(beef, frozenset({"meat"})), VariantOption(veggie)]

    result = assign_variants([Diner(vegetarian)], {vegetarian: {"meat"}}, variants, manual={vegetarian: beef})
    assert result.by_person == {vegetarian: beef}
    assert result.conflicts == {vegetarian: {"meat"}}


def test_portions_use_the_appetite_factors():
    small, normal, large = uuid4(), uuid4(), uuid4()
    variant = uuid4()
    diners = [Diner(small, Appetite.SMALL), Diner(normal), Diner(large, Appetite.LARGE)]
    variants = [VariantOption(variant)]
    assignment = assign_variants(diners, {}, variants)

    assert portions_by_variant(diners, assignment, variants) == {variant: Decimal("3.00")}


def test_leftovers_go_to_the_first_variant_with_persons_and_overrides_replace_the_count():
    person = uuid4()
    empty, used = uuid4(), uuid4()
    variants = [VariantOption(empty, frozenset({"meat"})), VariantOption(used)]
    diners = [Diner(person)]
    assignment = assign_variants(diners, {person: {"meat"}}, variants)

    assert portions_by_variant(diners, assignment, variants, leftover_portions=2) == {
        empty: Decimal("0"),
        used: Decimal("3"),
    }
    assert portions_by_variant(diners, assignment, variants, overrides={empty: 4})[empty] == Decimal("4")


def test_scale_needs_the_servings_of_the_recipe():
    assert scale_for(Decimal("6"), 4) == Decimal("1.5")
    with pytest.raises(MissingServingsError):
        scale_for(Decimal("6"), 0, recipe_name="Burger")
    with pytest.raises(MissingServingsError):
        scale_for(Decimal("6"), None)
