from uuid import uuid4

import pytest

from mealie.schema.personal.enums import FindingCode, VerificationSource, VerificationStatus
from mealie.services.personal.engine.compliance import (
    IngredientView,
    StatusBook,
    StoredStatus,
    ToolView,
    evaluate_ingredient,
    evaluate_recipe,
)
from mealie.services.personal.engine.rules import classify_text


@pytest.mark.parametrize(
    "text",
    ["Farine de blé", "blé", "Orge perlé", "pain de seigle", "Boulgour", "Dinkelmehl dinkel", "Malt d'orge", "seitan"],
)
def test_gluten_grains_are_incompatible(text: str):
    result = classify_text(text, "gluten")
    assert result is not None
    assert result.status == VerificationStatus.INCOMPATIBLE
    assert result.code == FindingCode.RULE_MATCH


@pytest.mark.parametrize(
    "text", ["Flocons d'avoine", "Sauce soja", "Bouillon cube", "Pain burger", "Saucisse de veau", "Bière blonde"]
)
def test_processed_foods_and_oats_need_a_label_check(text: str):
    result = classify_text(text, "gluten")
    assert result is not None
    assert result.status == VerificationStatus.UNVERIFIED
    assert result.code == FindingCode.LABEL_CHECK


@pytest.mark.parametrize("text", ["Tomate", "Farine de riz", "Blé noir", "Sarrasin", "Sable de Camargue", "Blette"])
def test_unknown_or_exception_foods_match_no_gluten_rule(text: str):
    assert classify_text(text, "gluten") is None


@pytest.mark.parametrize("text", ["Pâtes sans gluten", "Pain burger sans gluten", "Glutenfrei Brot"])
def test_a_gluten_free_name_is_a_claim_and_not_a_proof(text: str):
    result = classify_text(text, "gluten")
    assert result is not None
    assert result.status == VerificationStatus.UNVERIFIED
    assert result.code == FindingCode.FREE_CLAIM


def test_rules_never_return_verified():
    samples = ["tomate", "eau", "sel", "pâtes sans gluten", "steak végétal", "lait de coco", "riz"]
    for key in ["gluten", "meat", "fish", "dairy", "egg", "tree_nut"]:
        for sample in samples:
            result = classify_text(sample, key)
            assert result is None or result.status != VerificationStatus.VERIFIED


def test_meat_and_fish_rules():
    assert classify_text("Steak haché de boeuf", "meat").status == VerificationStatus.INCOMPATIBLE
    assert classify_text("Lardons fumés", "meat").status == VerificationStatus.INCOMPATIBLE
    assert classify_text("Filet de saumon", "fish").status == VerificationStatus.INCOMPATIBLE
    assert classify_text("Steak végétal", "meat").code == FindingCode.FREE_CLAIM
    assert classify_text("Amandes rôties", "meat") is None
    assert classify_text("Pâte feuilletée", "meat") is None
    assert classify_text("Galette de haricots", "meat") is None


def test_plant_milks_are_not_flagged_as_dairy():
    assert classify_text("Lait de coco", "dairy") is None
    assert classify_text("Lait entier", "dairy").status == VerificationStatus.INCOMPATIBLE


def test_ingredient_without_data_is_unverified():
    ingredient = IngredientView(display="2 tomates", food_id=uuid4(), food_name="Tomate")
    finding = evaluate_ingredient(ingredient, "gluten", StatusBook())
    assert finding is not None
    assert finding.status == VerificationStatus.UNVERIFIED
    assert finding.code == FindingCode.NO_DATA


def test_free_text_ingredient_is_unverified():
    finding = evaluate_ingredient(IngredientView(display="une pincée de magie"), "gluten", StatusBook())
    assert finding is not None
    assert finding.status == VerificationStatus.UNVERIFIED
    assert finding.code == FindingCode.FREE_TEXT


def test_free_text_ingredient_with_gluten_is_incompatible():
    finding = evaluate_ingredient(IngredientView(display="200 g de farine de blé"), "gluten", StatusBook())
    assert finding is not None
    assert finding.status == VerificationStatus.INCOMPATIBLE


def test_manually_verified_food_has_no_finding():
    food_id = uuid4()
    book = StatusBook(foods={(food_id, "gluten"): StoredStatus(VerificationStatus.VERIFIED, VerificationSource.MANUAL)})
    ingredient = IngredientView(display="pain burger", food_id=food_id, food_name="Pain burger")
    assert evaluate_ingredient(ingredient, "gluten", book) is None


@pytest.mark.parametrize(
    "source", [VerificationSource.AI_SUGGESTION, VerificationSource.RULE, VerificationSource.PRODUCT_LABEL]
)
def test_verified_state_from_a_non_manual_source_does_not_count(source: VerificationSource):
    food_id = uuid4()
    book = StatusBook(foods={(food_id, "gluten"): StoredStatus(VerificationStatus.VERIFIED, source)})
    finding = evaluate_ingredient(IngredientView(display="x", food_id=food_id, food_name="x"), "gluten", book)
    assert finding is not None
    assert finding.status == VerificationStatus.UNVERIFIED


def test_stored_incompatible_state_wins_over_rules():
    food_id = uuid4()
    book = StatusBook(
        foods={(food_id, "gluten"): StoredStatus(VerificationStatus.INCOMPATIBLE, VerificationSource.MANUAL, "traces")}
    )
    finding = evaluate_ingredient(IngredientView(display="riz", food_id=food_id, food_name="Riz"), "gluten", book)
    assert finding is not None
    assert finding.status == VerificationStatus.INCOMPATIBLE
    assert finding.detail == "traces"


def test_recipe_status_is_the_worst_ingredient_status():
    verified_id, unknown_id = uuid4(), uuid4()
    book = StatusBook(
        foods={(verified_id, "gluten"): StoredStatus(VerificationStatus.VERIFIED, VerificationSource.MANUAL)}
    )
    verified = IngredientView(display="riz", food_id=verified_id, food_name="Riz")
    unknown = IngredientView(display="tomate", food_id=unknown_id, food_name="Tomate")
    wheat = IngredientView(display="farine", food_id=uuid4(), food_name="Farine de blé")

    assert evaluate_recipe([verified], {"gluten"}, book).statuses["gluten"] == VerificationStatus.VERIFIED
    assert evaluate_recipe([verified, unknown], {"gluten"}, book).statuses["gluten"] == VerificationStatus.UNVERIFIED
    result = evaluate_recipe([verified, unknown, wheat], {"gluten"}, book)
    assert result.statuses["gluten"] == VerificationStatus.INCOMPATIBLE
    assert result.incompatible_keys() == {"gluten"}


def test_recipe_without_ingredients_is_unverified():
    result = evaluate_recipe([], {"gluten"}, StatusBook())
    assert result.statuses["gluten"] == VerificationStatus.UNVERIFIED
    assert result.findings[0].code == FindingCode.NO_INGREDIENTS


def test_flagged_tool_keeps_a_whole_preparation_unverified():
    food_id, tool_id = uuid4(), uuid4()
    book = StatusBook(
        foods={(food_id, "gluten"): StoredStatus(VerificationStatus.VERIFIED, VerificationSource.MANUAL)},
        tools={(tool_id, "gluten"): "grille-pain partagé"},
    )
    ingredients = [IngredientView(display="riz", food_id=food_id, food_name="Riz")]
    tools = [ToolView(tool_id, "Grille-pain")]

    without_scope = evaluate_recipe(ingredients, {"gluten"}, book, tools)
    assert without_scope.statuses["gluten"] == VerificationStatus.VERIFIED

    with_scope = evaluate_recipe(ingredients, {"gluten"}, book, tools, tool_check_keys={"gluten"})
    assert with_scope.statuses["gluten"] == VerificationStatus.UNVERIFIED
    assert with_scope.findings[0].code == FindingCode.TOOL_CHECK
    assert with_scope.findings[0].kind == "tool"
