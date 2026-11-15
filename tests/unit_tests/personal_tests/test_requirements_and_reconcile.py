from decimal import Decimal
from uuid import uuid4

from mealie.schema.personal.enums import ShoppingPlanLineState
from mealie.services.personal.engine.reconcile import (
    ACTION_CREATE,
    ACTION_DELETE,
    ACTION_NONE,
    ACTION_UPDATE,
    ItemState,
    LedgerState,
    reconcile_line,
)
from mealie.services.personal.engine.requirements import (
    Need,
    NeedSource,
    Packaging,
    StockEntry,
    aggregate,
    apply_packaging,
    apply_stock,
)
from mealie.services.personal.engine.units import UnitInfo, convert

GRAM = UnitInfo(uuid4(), "gramme", Decimal("1"), "gram")
KILOGRAM = UnitInfo(uuid4(), "kilogramme", Decimal("1"), "kilogram")
MILLILITER = UnitInfo(uuid4(), "millilitre", Decimal("1"), "milliliter")
LITER = UnitInfo(uuid4(), "litre", Decimal("1"), "liter")
TABLESPOON = UnitInfo(uuid4(), "cuillère à soupe", Decimal("15"), "milliliter")
PINCH = UnitInfo(uuid4(), "pincée")
CLOVE = UnitInfo(uuid4(), "gousse")


def source(name: str = "Recette") -> NeedSource:
    return NeedSource(uuid4(), name, Decimal("1"), Decimal("1"))


def need(food_id, quantity, unit=None, name="Tomate", recipe="Recette") -> Need:
    return Need(Decimal(str(quantity)), source(recipe), food_id=food_id, food_name=name, unit=unit)


def test_unit_conversion_is_exact_for_metric_units():
    assert convert(Decimal("1.5"), KILOGRAM, GRAM) == Decimal("1500")
    assert convert(Decimal("250"), GRAM, KILOGRAM) == Decimal("0.25")
    assert convert(Decimal("2"), TABLESPOON, MILLILITER) == Decimal("30")
    assert convert(Decimal("3"), None, None) == Decimal("3")


def test_incompatible_units_do_not_convert():
    assert convert(Decimal("1"), GRAM, MILLILITER) is None
    assert convert(Decimal("1"), PINCH, GRAM) is None
    assert convert(Decimal("1"), None, GRAM) is None
    assert convert(Decimal("1"), PINCH, CLOVE) is None


def test_same_food_from_two_recipes_is_added():
    tomato = uuid4()
    lines = aggregate([need(tomato, 400, GRAM, recipe="A"), need(tomato, 300, GRAM, recipe="B")])

    assert len(lines) == 1
    assert lines[0].quantity_needed == Decimal("700")
    assert lines[0].unit == GRAM
    assert [s.recipe_name for s in lines[0].sources] == ["A", "B"]


def test_compatible_units_are_merged_into_one_line():
    flour = uuid4()
    lines = aggregate([need(flour, 750, GRAM, "Farine"), need(flour, 0.5, KILOGRAM, "Farine")])

    assert len(lines) == 1
    assert lines[0].unit == KILOGRAM
    assert lines[0].quantity_needed == Decimal("1.25")


def test_small_merged_quantity_uses_the_small_unit():
    flour = uuid4()
    lines = aggregate([need(flour, 100, GRAM, "Farine"), need(flour, 0.2, KILOGRAM, "Farine")])
    assert lines[0].unit == GRAM
    assert lines[0].quantity_needed == Decimal("300")


def test_incompatible_units_stay_on_separate_lines():
    garlic = uuid4()
    lines = aggregate([need(garlic, 2, CLOVE, "Ail"), need(garlic, 10, GRAM, "Ail"), need(garlic, 1, None, "Ail")])

    assert len(lines) == 3
    assert sorted(str(line.quantity_needed) for line in lines) == ["1", "10", "2"]


def test_ingredients_without_food_merge_on_their_text():
    first = Need(Decimal("1"), source(), note="Sel  fin")
    second = Need(Decimal("2"), source(), note="sel fin")
    other = Need(Decimal("1"), source(), note="poivre")

    lines = aggregate([first, second, other])
    assert len(lines) == 2
    assert {line.note: line.quantity_needed for line in lines} == {"Sel  fin": Decimal("3"), "poivre": Decimal("1")}


def test_preferred_unit_keeps_the_line_unit_stable():
    flour = uuid4()
    needs = [need(flour, 2, KILOGRAM, "Farine")]
    key = aggregate(needs)[0].key

    lines = aggregate(needs, preferred_units={key: GRAM})
    assert lines[0].unit == GRAM
    assert lines[0].quantity_needed == Decimal("2000")


def test_aggregation_is_deterministic():
    foods = [uuid4() for _ in range(5)]
    needs = [need(food, 0.1 * (i + 1), GRAM, name=f"Aliment {i}") for i, food in enumerate(foods)] * 3
    first = aggregate(needs)
    second = aggregate(list(reversed(needs)))

    assert [(line.key, line.quantity_needed) for line in first] == [(line.key, line.quantity_needed) for line in second]
    assert first[0].quantity_needed == Decimal("0.3")


def test_confirmed_stock_is_subtracted():
    tomato = uuid4()
    lines = aggregate([need(tomato, 400, GRAM, recipe="A"), need(tomato, 300, GRAM, recipe="B")])
    apply_stock(lines, [StockEntry(tomato, Decimal("200"), GRAM)])

    assert lines[0].quantity_needed == Decimal("700")
    assert lines[0].quantity_from_stock == Decimal("200")
    assert lines[0].quantity_to_buy == Decimal("500")


def test_stock_in_another_compatible_unit_is_converted():
    flour = uuid4()
    lines = aggregate([need(flour, 750, GRAM, "Farine")])
    apply_stock(lines, [StockEntry(flour, Decimal("0.5"), KILOGRAM)])

    assert lines[0].quantity_from_stock == Decimal("500")
    assert lines[0].quantity_to_buy == Decimal("250")


def test_stock_larger_than_the_need_covers_the_line_only():
    rice = uuid4()
    lines = aggregate([need(rice, 300, GRAM, "Riz")])
    apply_stock(lines, [StockEntry(rice, Decimal("1"), KILOGRAM)])

    assert lines[0].quantity_from_stock == Decimal("300")
    assert lines[0].quantity_to_buy == Decimal("0")


def test_stock_in_an_incompatible_unit_is_not_subtracted():
    garlic = uuid4()
    lines = aggregate([need(garlic, 2, CLOVE, "Ail")])
    apply_stock(lines, [StockEntry(garlic, Decimal("50"), GRAM)])

    assert lines[0].quantity_from_stock == Decimal("0")
    assert lines[0].quantity_to_buy == Decimal("2")
    assert lines[0].stock_warnings == ["UNIT_MISMATCH"]


def test_one_stock_entry_is_not_used_twice():
    garlic = uuid4()
    lines = aggregate([need(garlic, 30, GRAM, "Ail"), need(garlic, 0.05, LITER, "Ail")])
    apply_stock(lines, [StockEntry(garlic, Decimal("40"), GRAM), StockEntry(garlic, Decimal("20"), MILLILITER)])

    by_unit = {line.unit.name: line for line in lines}
    assert by_unit["gramme"].quantity_from_stock == Decimal("30")
    assert by_unit["litre"].quantity_from_stock == Decimal("0.02")
    assert by_unit["litre"].quantity_to_buy == Decimal("0.03")


def test_quantity_to_buy_is_rounded_up_to_whole_packs():
    flour = uuid4()
    lines = aggregate([need(flour, 1250, GRAM, "Farine")])
    apply_packaging(lines, {flour: Packaging(Decimal("1"), KILOGRAM, "paquet 1 kg")})

    assert lines[0].quantity_needed == Decimal("1250")
    assert lines[0].packs == 2
    assert lines[0].quantity_to_buy == Decimal("2000")
    assert lines[0].pack_label == "paquet 1 kg"


def test_exact_multiple_of_a_pack_is_not_rounded_further():
    butter = uuid4()
    lines = aggregate([need(butter, 500, GRAM, "Beurre")])
    apply_packaging(lines, {butter: Packaging(Decimal("250"), GRAM)})
    assert lines[0].packs == 2
    assert lines[0].quantity_to_buy == Decimal("500")


def test_nothing_to_buy_means_no_pack():
    rice = uuid4()
    lines = aggregate([need(rice, 300, GRAM, "Riz")])
    apply_stock(lines, [StockEntry(rice, Decimal("1"), KILOGRAM)])
    apply_packaging(lines, {rice: Packaging(Decimal("1"), KILOGRAM)})

    assert lines[0].packs is None
    assert lines[0].quantity_to_buy == Decimal("0")


def test_food_counted_by_the_piece_is_rounded_up_to_whole_pieces():
    bun, flour = uuid4(), uuid4()
    lines = aggregate([need(bun, 4.25, None, "Pain burger"), need(flour, 487.5, GRAM, "Farine")])
    apply_packaging(lines, {})

    by_name = {line.food_name: line for line in lines}
    assert by_name["Pain burger"].quantity_needed == Decimal("4.25")
    assert by_name["Pain burger"].quantity_to_buy == Decimal("5")
    # a food with a unit of measure keeps its exact quantity
    assert by_name["Farine"].quantity_to_buy == Decimal("487.5")


def test_whole_pieces_are_not_rounded_further():
    egg = uuid4()
    lines = aggregate([need(egg, 6, None, "Oeuf")])
    apply_packaging(lines, {})
    assert lines[0].quantity_to_buy == Decimal("6")


def test_packaging_in_an_incompatible_unit_is_ignored():
    garlic = uuid4()
    lines = aggregate([need(garlic, 2, CLOVE, "Ail")])
    apply_packaging(lines, {garlic: Packaging(Decimal("100"), GRAM)})
    assert lines[0].packs is None
    assert lines[0].quantity_to_buy == Decimal("2")


# ----------------------------------------------------------------------------------------------------------------
# Reconciliation


def test_new_line_creates_an_item():
    result = reconcile_line("k", Decimal("500"), None, None)
    assert result.action == ACTION_CREATE
    assert result.item_quantity == Decimal("500")
    assert result.ledger.projected_quantity == Decimal("500")


def test_unchanged_line_does_nothing():
    item_id = uuid4()
    ledger = LedgerState("k", projected_quantity=Decimal("500"), item_id=item_id)
    result = reconcile_line("k", Decimal("500"), ledger, ItemState(item_id, Decimal("500"), False))
    assert result.action == ACTION_NONE


def test_changed_need_updates_the_open_item():
    item_id = uuid4()
    ledger = LedgerState("k", projected_quantity=Decimal("500"), item_id=item_id)
    result = reconcile_line("k", Decimal("800"), ledger, ItemState(item_id, Decimal("500"), False))
    assert result.action == ACTION_UPDATE
    assert result.item_quantity == Decimal("800")


def test_manual_adjustment_is_kept_when_the_need_changes():
    item_id = uuid4()
    ledger = LedgerState("k", projected_quantity=Decimal("500"), item_id=item_id)
    # the user raised the item from 500 to 650
    result = reconcile_line("k", Decimal("800"), ledger, ItemState(item_id, Decimal("650"), False))
    assert result.action == ACTION_UPDATE
    assert result.item_quantity == Decimal("950")
    assert result.ledger.projected_quantity == Decimal("800")


def test_manual_reduction_is_kept_when_the_need_changes():
    item_id = uuid4()
    ledger = LedgerState("k", projected_quantity=Decimal("500"), item_id=item_id)
    result = reconcile_line("k", Decimal("600"), ledger, ItemState(item_id, Decimal("300"), False))
    assert result.item_quantity == Decimal("400")


def test_bought_item_is_not_created_again():
    item_id = uuid4()
    ledger = LedgerState("k", projected_quantity=Decimal("500"), item_id=item_id)
    result = reconcile_line("k", Decimal("500"), ledger, ItemState(item_id, Decimal("500"), True))

    assert result.action == ACTION_NONE
    assert result.ledger.purchased_quantity == Decimal("500")
    assert result.ledger.item_id is None

    again = reconcile_line("k", Decimal("500"), result.ledger, None)
    assert again.action == ACTION_NONE


def test_bought_item_plus_a_larger_need_creates_only_the_missing_part():
    item_id = uuid4()
    ledger = LedgerState("k", projected_quantity=Decimal("500"), item_id=item_id)
    result = reconcile_line("k", Decimal("700"), ledger, ItemState(item_id, Decimal("500"), True))

    assert result.action == ACTION_CREATE
    assert result.item_quantity == Decimal("200")
    assert result.ledger.purchased_quantity == Decimal("500")


def test_deleted_item_is_not_created_again_unless_asked():
    ledger = LedgerState("k", projected_quantity=Decimal("500"), item_id=uuid4())
    result = reconcile_line("k", Decimal("500"), ledger, None)
    assert result.action == ACTION_NONE
    assert result.ledger.state == ShoppingPlanLineState.DISMISSED

    still = reconcile_line("k", Decimal("900"), result.ledger, None)
    assert still.action == ACTION_NONE

    restored = reconcile_line("k", Decimal("900"), still.ledger, None, restore_dismissed=True)
    assert restored.action == ACTION_CREATE
    assert restored.item_quantity == Decimal("900")


def test_line_no_longer_needed_removes_the_item():
    item_id = uuid4()
    ledger = LedgerState("k", projected_quantity=Decimal("500"), item_id=item_id)
    result = reconcile_line("k", Decimal("0"), ledger, ItemState(item_id, Decimal("500"), False))
    assert result.action == ACTION_DELETE
    assert result.ledger.state == ShoppingPlanLineState.OBSOLETE


def test_line_no_longer_needed_keeps_the_manual_part_of_the_item():
    item_id = uuid4()
    ledger = LedgerState("k", projected_quantity=Decimal("500"), item_id=item_id)
    result = reconcile_line("k", Decimal("0"), ledger, ItemState(item_id, Decimal("700"), False))
    assert result.action == ACTION_UPDATE
    assert result.item_quantity == Decimal("200")
