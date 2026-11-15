from datetime import date
from decimal import Decimal
from uuid import uuid4

from mealie.services.personal.engine.pricing import (
    PricePoint,
    cheapest_used,
    compare_baskets,
    cost_of,
    costs_of,
    price_point,
)
from mealie.services.personal.engine.units import UnitInfo
from mealie.services.personal.price_source import PriceSource, parse_offer

GRAM = UnitInfo(uuid4(), "gramme", Decimal("1"), "gram")
KILO = UnitInfo(uuid4(), "kilogramme", Decimal("1"), "kilogram")
DECILITER = UnitInfo(uuid4(), "décilitre", Decimal("100"), "milliliter")
PINCH = UnitInfo(uuid4(), "pincée")


def point(store: str, price: str, size: str | None, unit: str | None, **extra) -> PricePoint:
    return price_point(store, Decimal(price), Decimal(size) if size else None, unit, **extra)


def test_a_quantity_is_rounded_up_to_whole_packs():
    flour = point("migros", "1.90", "1", "kg")

    cost = cost_of(Decimal("1200"), GRAM, flour)
    assert cost is not None
    # 1.2 kg needs two packs of 1 kg; the recipe uses 1.2 packs of them
    assert (cost.packs, cost.cost, cost.used_cost) == (2, Decimal("3.80"), Decimal("2.28"))

    exact = cost_of(Decimal("2"), KILO, flour)
    assert exact is not None and (exact.packs, exact.cost) == (2, Decimal("3.80"))


def test_a_food_sold_by_weight_is_not_rounded():
    carrots = point("coop", "2.60", "1", "kg", by_weight=True)
    cost = cost_of(Decimal("350"), GRAM, carrots)
    assert cost is not None
    assert (cost.packs, cost.cost, cost.used_cost) == (None, Decimal("0.91"), Decimal("0.91"))


def test_pieces_and_weights_are_never_mixed():
    onions_by_kilo = point("migros", "2.20", "1", "kg")
    eggs = point("migros", "4.50", "6", "piece")

    # "2 onions" against a price per kilogram: the function does not guess the weight of an onion
    assert cost_of(Decimal("2"), None, onions_by_kilo) is None
    assert cost_of(Decimal("200"), GRAM, eggs) is None
    # a unit without a standard size cannot be priced
    assert cost_of(Decimal("1"), PINCH, onions_by_kilo) is None

    cost = cost_of(Decimal("7"), None, eggs)
    assert cost is not None and (cost.packs, cost.cost, cost.used_cost) == (2, Decimal("9.00"), Decimal("5.25"))


def test_a_price_without_a_size_counts_as_one_piece():
    lettuce = point("aldi", "1.49", None, None)
    cost = cost_of(Decimal("2"), None, lettuce)
    assert cost is not None and (cost.packs, cost.cost) == (2, Decimal("2.98"))
    assert cost_of(Decimal("200"), GRAM, lettuce) is None


def test_volumes_convert_between_units():
    cream = point("coop", "2.95", "2.5", "l")
    assert cream.size == Decimal("2500")
    cost = cost_of(Decimal("3"), DECILITER, cream)
    assert cost is not None and (cost.packs, cost.used_cost) == (1, Decimal("0.35"))


def test_costs_are_sorted_and_the_cheapest_use_is_found():
    points = [
        point("coop", "2.40", "500", "g"),
        point("migros", "1.90", "1", "kg"),
        point("lidl", "0.99", "6", "piece"),
    ]
    costs = costs_of(Decimal("400"), GRAM, points)
    # the price by the piece cannot price grams and is left out
    assert [(cost.store, cost.cost) for cost in costs] == [("migros", Decimal("1.90")), ("coop", Decimal("2.40"))]

    # the pack of Migros is cheaper to buy, and its 400 g also cost less
    best = cheapest_used(Decimal("400"), GRAM, points)
    assert best is not None and (best.store, best.used_cost) == ("migros", Decimal("0.76"))
    assert cheapest_used(Decimal("1"), PINCH, points) is None


def test_a_promotion_that_ended_gives_back_the_regular_price():
    today = date(2026, 11, 15)
    running = point(
        "migros",
        "1.50",
        "500",
        "g",
        regular_price=Decimal("2.10"),
        promotion="-30%",
        promotion_ends_on=date(2026, 11, 20),
        today=today,
    )
    assert (running.price, running.on_promotion) == (Decimal("1.50"), True)

    ended = point(
        "migros",
        "1.50",
        "500",
        "g",
        regular_price=Decimal("2.10"),
        promotion="-30%",
        promotion_ends_on=date(2026, 11, 14),
        today=today,
    )
    assert (ended.price, ended.on_promotion) == (Decimal("2.10"), False)

    plain = point("migros", "1.50", "500", "g", today=today)
    assert plain.on_promotion is False


def test_offer_parsing_keeps_only_what_is_sure():
    offer = parse_offer(
        {
            "chain": "migros",
            "id": "104074100000",
            "name": "M-Classic Spaghetti",
            "brand": "M-Classic",
            "size": {"value": 750, "unit": "g"},
            "price": {"current": 1.6, "regular": 2.0, "currency": "CHF"},
            "unitPrice": {"value": 2.13, "per": "kg"},
            "tags": ["budget", 7],
            "imageUrl": "https://image.migros.ch/x.jpg",
            "productUrl": "javascript:alert(1)",
            "promotion": {"endsAt": "2026-11-21T22:59:59.000Z", "description": "20%"},
        }
    )
    assert offer is not None
    assert (offer.store, offer.external_id, offer.price, offer.regular_price) == ("migros", "104074100000", 1.6, 2.0)
    assert (offer.size, offer.size_unit) == (750, "g")
    assert (offer.unit_price, offer.unit_price_per) == (2.13, "kg")
    assert offer.tags == ["budget"]
    assert offer.image_url == "https://image.migros.ch/x.jpg"
    # an address that is not http is dropped
    assert offer.product_url is None
    assert (offer.promotion, offer.promotion_ends_on) == ("20%", date(2026, 11, 21))

    # a regular price that is not above the price is not a reduction; an unknown size unit is not a size
    plain = parse_offer(
        {
            "chain": "lidl",
            "id": 9,
            "name": "Pain",
            "price": {"current": 2, "regular": 2},
            "size": {"value": 1, "unit": "x"},
        }
    )
    assert plain is not None and (plain.regular_price, plain.size, plain.size_unit) == (None, None, None)

    for broken in (
        None,
        {},
        {"chain": "coop", "id": "1", "name": "x"},
        {"chain": "coop", "id": "1", "price": {"current": 1}},
    ):
        assert parse_offer(broken) is None
    assert parse_offer({"chain": "coop", "id": "1", "name": "x", "price": {"current": 0}}) is None


def test_a_former_price_given_as_text_is_read_as_the_regular_price():
    def offer(description: str, regular: float | None = None):
        price = {"current": 17.99} | ({"regular": regular} if regular else {})
        product = {"chain": "aldi", "id": "1", "name": "Kaffee", "price": price}
        return parse_offer(product | {"promotion": {"description": description}})

    read = offer("Was: CHF 22.95")
    assert read is not None and (read.regular_price, read.promotion) == (22.95, None)
    comma = offer("statt 22,95")
    assert comma is not None and (comma.regular_price, comma.promotion) == (22.95, None)

    # a text that says more than a price stays a label; a price that is not above the price is no reduction
    label = offer("-25% dès 2 pièces")
    assert label is not None and (label.regular_price, label.promotion) == (None, "-25% dès 2 pièces")
    lower = offer("Was: CHF 9.95")
    assert lower is not None and (lower.regular_price, lower.promotion) == (None, None)

    # the regular price of the shop wins over the text
    both = offer("Was: CHF 30.00", regular=22.95)
    assert both is not None and (both.regular_price, both.promotion) == (22.95, "Was: CHF 30.00")


def test_a_product_with_another_id_is_not_the_product_asked_for(monkeypatch):
    answer = {"chain": "migros", "id": "522205600000", "name": "Lactase", "price": {"current": 9.9}}
    monkeypatch.setattr(PriceSource, "_call", lambda self, tool, arguments: {"product": answer})
    source = PriceSource("http://price-bridge:8080")

    found = source.product("migros", "522205600000")
    assert found is not None and found.price == 9.9
    # the shop answered an unknown id with another product
    assert source.product("migros", "000000000000") is None
    assert source.product("coop", "522205600000") is None


def test_the_price_source_is_off_without_an_address(monkeypatch):
    monkeypatch.delenv("PE_PRICE_SOURCE_URL", raising=False)
    assert PriceSource().enabled is False
    assert PriceSource("file:///etc/passwd").enabled is False
    assert PriceSource("http://price-bridge:8080/").base_url == "http://price-bridge:8080"


def test_a_usual_weight_prices_pieces_against_a_pack_by_weight():
    onions = point("migros", "2.20", "1", "kg")

    # the engine guesses nothing by itself
    assert cost_of(Decimal("4"), None, onions) is None

    # 4 onions of 150 g are 600 g: one pack, and the recipe uses 60 % of it
    cost = cost_of(Decimal("4"), None, onions, piece_size=Decimal("150"))
    assert cost is not None
    assert (cost.cost, cost.used_cost, cost.packs, cost.approximate) == (Decimal("2.20"), Decimal("1.32"), 1, True)

    # a usual weight says nothing about a volume, and nothing about a unit such as a pinch
    assert cost_of(Decimal("4"), None, point("coop", "1.80", "1", "l"), piece_size=Decimal("150")) is None
    assert cost_of(Decimal("1"), PINCH, onions, piece_size=Decimal("150")) is None

    # a quantity that the pack measures is exact, with or without the assumptions
    exact = cost_of(Decimal("600"), GRAM, onions, piece_size=Decimal("150"), assume_pack=True)
    assert exact is not None and exact.approximate is False


def test_the_shopping_takes_one_pack_when_nothing_measures_the_quantity():
    parsley = point("migros", "1.50", "30", "g")

    cost = cost_of(Decimal("2"), PINCH, parsley, assume_pack=True)
    assert cost is not None
    assert (cost.cost, cost.used_cost, cost.packs, cost.approximate) == (Decimal("1.50"), Decimal("1.50"), 1, True)

    # the share of a pack that a recipe uses is never assumed
    assert cheapest_used(Decimal("2"), PINCH, [parsley]) is None
    assert costs_of(Decimal("2"), PINCH, [parsley]) == []


def test_the_shops_are_compared_on_the_whole_shopping():
    lines = [
        {"migros": Decimal("2.00"), "coop": Decimal("3.00")},
        {"migros": Decimal("9.00"), "coop": Decimal("5.00")},
        {"migros": Decimal("4.00"), "coop": Decimal("4.50"), "lidl": Decimal("1.00")},
        {},
    ]

    baskets = compare_baskets(lines)
    # Migros is cheaper on two lines of three, and Coop is cheaper for the whole shopping
    assert [(basket.store, basket.basket, basket.comparable) for basket in baskets] == [
        ("coop", Decimal("12.50"), True),
        ("migros", Decimal("15.00"), True),
        ("lidl", Decimal("10.50"), False),
    ]

    # Lidl has one price of three: the two other lines count at the mean of Migros and Coop
    lidl = baskets[-1]
    assert (lidl.total, lidl.estimated, lidl.priced, lidl.missing) == (Decimal("1.00"), Decimal("9.50"), 1, 2)

    # a line that no shop prices is in no total, and no shop means no basket
    assert all(basket.priced + basket.missing == 3 for basket in baskets)
    assert compare_baskets([{}, {}]) == []
