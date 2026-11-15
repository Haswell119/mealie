from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mealie.services.personal.price_source import PriceSource, PriceSourceUnavailable
from tests.utils.fixture_schemas import TestUser

from .helpers import BASE, create_food, create_recipe, create_unit, purge_orphans
from .test_shopping_plans import add_stock, recipes_plan

PRICES = f"{BASE}/prices"
PLANS = f"{BASE}/shopping-plans"

SPAGHETTI = {
    "chain": "migros",
    "id": "104074100000",
    "name": "M-Classic Spaghetti",
    "brand": "M-Classic",
    "size": {"value": 750, "unit": "g"},
    "price": {"current": 1.6, "regular": 2.0, "currency": "CHF"},
    "unitPrice": {"value": 2.13, "per": "kg"},
    "tags": ["budget"],
    "promotion": {"endsAt": "2099-01-01T00:00:00.000Z", "description": "20%"},
}
COOP_SPAGHETTI = {
    "chain": "coop",
    "id": "3046920",
    "name": "Qualité & Prix Spaghetti",
    "size": {"value": 500, "unit": "g"},
    "price": {"current": 0.95, "currency": "CHF"},
    "unitPrice": {"value": 1.9, "per": "kg"},
    "tags": [],
}


@pytest.fixture()
def price_source(monkeypatch: pytest.MonkeyPatch):
    """Replaces the network call of the price service and records what the application asks for."""
    calls: list[tuple[str, dict]] = []
    state = {"fail": False, "products": {("migros", SPAGHETTI["id"]): SPAGHETTI}}

    def fake_call(self, tool: str, arguments: dict):
        calls.append((tool, arguments))
        if state["fail"]:
            raise PriceSourceUnavailable()
        if tool == "get_product":
            product = state["products"].get((arguments["chain"], arguments["id"]))
            return {"product": product} if product else None
        return {
            "byChain": {"migros": [SPAGHETTI, {"chain": "migros", "id": "x"}], "coop": [COOP_SPAGHETTI], "lidl": []},
            "errors": [{"chain": "lidl", "code": "unavailable"}],
        }

    monkeypatch.setenv("PE_PRICE_SOURCE_URL", "http://price-bridge:8080")
    monkeypatch.setattr(PriceSource, "_call", fake_call)
    return calls, state


def named(name: str) -> str:
    """A food name that no other test uses: the name of a food is unique in a group."""
    return f"{name} {uuid4().hex[:6]}"


def save_price(api_client: TestClient, user: TestUser, food, store: str, price: float, **fields) -> dict:
    payload = {"foodId": str(food.id), "store": store, "price": price, **fields}
    response = api_client.post(PRICES, json=payload, headers=user.token)
    assert response.status_code == 201, response.text
    return response.json()


def test_price_crud_keeps_one_price_for_each_food_and_shop(api_client: TestClient, unique_user: TestUser):
    flour = create_food(unique_user, named("Farine"))

    first = save_price(api_client, unique_user, flour, " Migros ", 1.9, size=1, sizeUnit="kg", label="Farine blanche")
    assert (first["store"], first["price"], first["size"], first["sizeUnit"]) == ("migros", 1.9, 1, "kg")
    assert (first["source"], first["currency"], first["food"]["name"]) == ("manual", "CHF", flour.name)

    # a second price for the same food and shop replaces the first
    again = save_price(api_client, unique_user, flour, "migros", 1.7, size=1, sizeUnit="kg")
    assert again["id"] == first["id"] and again["price"] == 1.7
    coop = save_price(api_client, unique_user, flour, "coop", 2.1, size=1, sizeUnit="kg")

    listed = api_client.get(PRICES, params={"perPage": -1}, headers=unique_user.token).json()["items"]
    assert sorted(price["store"] for price in listed) == ["coop", "migros"]

    # an update cannot create a second price for a shop that already has one
    clash = api_client.put(
        f"{PRICES}/{coop['id']}",
        json={"foodId": str(flour.id), "store": "migros", "price": 2},
        headers=unique_user.token,
    )
    assert clash.status_code == 400 and clash.json()["detail"]["exception"] == "PRICE_EXISTS"

    updated = api_client.put(
        f"{PRICES}/{coop['id']}",
        json={"foodId": str(flour.id), "store": "marché", "price": 3, "size": 1, "sizeUnit": "kg", "byWeight": True},
        headers=unique_user.token,
    )
    assert updated.status_code == 200, updated.text
    assert (updated.json()["store"], updated.json()["byWeight"]) == ("marché", True)

    assert api_client.delete(f"{PRICES}/{coop['id']}", headers=unique_user.token).status_code == 200
    assert api_client.get(f"{PRICES}/{coop['id']}", headers=unique_user.token).status_code == 404


def test_price_validation(api_client: TestClient, unique_user: TestUser):
    food = create_food(unique_user)
    base = {"foodId": str(food.id), "store": "migros", "price": 2}

    for bad in (
        {**base, "price": 0},
        {**base, "size": 500},
        {**base, "sizeUnit": "g"},
        {**base, "size": 500, "sizeUnit": "stone"},
        {**base, "store": " "},
        {**base, "productUrl": "javascript:alert(1)"},
    ):
        assert api_client.post(PRICES, json=bad, headers=unique_user.token).status_code == 422, bad

    below = api_client.post(PRICES, json={**base, "regularPrice": 1.5}, headers=unique_user.token)
    assert below.status_code == 400 and below.json()["detail"]["exception"] == "PRICE_ABOVE_REGULAR"

    missing = {**base, "foodId": "00000000-0000-4000-8000-000000000000"}
    assert api_client.post(PRICES, json=missing, headers=unique_user.token).status_code == 404


def test_prices_belong_to_one_household(api_client: TestClient, unique_user: TestUser, h2_user: TestUser):
    food = create_food(unique_user)
    price = save_price(api_client, unique_user, food, "migros", 2)

    assert api_client.get(f"{PRICES}/{price['id']}", headers=h2_user.token).status_code == 404
    listed = api_client.get(PRICES, params={"perPage": -1}, headers=h2_user.token).json()["items"]
    assert price["id"] not in [item["id"] for item in listed]


def test_deleting_a_food_removes_its_prices(api_client: TestClient, unique_user: TestUser):
    food = create_food(unique_user)
    price = save_price(api_client, unique_user, food, "migros", 2)

    unique_user.repos.ingredient_foods.delete(food.id)
    purge_orphans(unique_user)
    assert api_client.get(f"{PRICES}/{price['id']}", headers=unique_user.token).status_code == 404


def test_the_application_works_without_a_price_source(api_client: TestClient, unique_user: TestUser, monkeypatch):
    monkeypatch.delenv("PE_PRICE_SOURCE_URL", raising=False)

    status = api_client.get(f"{PRICES}/status", headers=unique_user.token)
    assert status.status_code == 200 and status.json() == {"enabled": False, "name": None, "stores": []}

    offers = api_client.get(f"{PRICES}/offers", params={"query": "spaghetti"}, headers=unique_user.token)
    assert offers.status_code == 200
    assert offers.json() == {"query": "spaghetti", "store": None, "available": False, "offers": [], "failedStores": []}

    refreshed = api_client.post(f"{PRICES}/refresh", headers=unique_user.token)
    assert refreshed.status_code == 200 and refreshed.json()["available"] is False


def test_offer_search_carries_only_the_text_and_the_shops(api_client: TestClient, unique_user: TestUser, price_source):
    calls, state = price_source

    status = api_client.get(f"{PRICES}/status", headers=unique_user.token).json()
    assert status["enabled"] is True and status["stores"] == ["coop", "migros", "aldi", "lidl"]

    response = api_client.get(f"{PRICES}/offers", params={"query": " spaghetti "}, headers=unique_user.token)
    assert response.status_code == 200, response.text
    body = response.json()

    assert calls == [
        ("search_products", {"query": "spaghetti", "chains": ["coop", "migros", "aldi", "lidl"], "limit": 8})
    ]
    assert unique_user.email not in str(calls) and unique_user.username not in str(calls)

    # the cheapest price by the kilogram comes first; the product without a price is left out
    assert [(offer["store"], offer["externalId"]) for offer in body["offers"]] == [
        ("coop", "3046920"),
        ("migros", "104074100000"),
    ]
    migros = body["offers"][1]
    assert (migros["price"], migros["regularPrice"], migros["size"], migros["sizeUnit"]) == (1.6, 2.0, 750, "g")
    assert (migros["promotion"], migros["promotionEndsOn"]) == ("20%", "2099-01-01")
    # a shop that did not answer is named: its empty list does not mean "no product"
    assert body["failedStores"] == ["lidl"]

    one = api_client.get(f"{PRICES}/offers", params={"query": "spaghetti", "store": "coop"}, headers=unique_user.token)
    assert calls[-1][1]["chains"] == ["coop"]
    assert [offer["store"] for offer in one.json()["offers"]] == ["coop"]

    assert api_client.get(f"{PRICES}/offers", params={"query": "s"}, headers=unique_user.token).status_code == 400
    bad = api_client.get(f"{PRICES}/offers", params={"query": "pain", "store": "walmart"}, headers=unique_user.token)
    assert bad.status_code == 422

    state["fail"] = True
    down = api_client.get(f"{PRICES}/offers", params={"query": "spaghetti"}, headers=unique_user.token)
    assert down.status_code == 200 and down.json()["available"] is False


def test_refresh_reads_again_the_prices_of_the_source(api_client: TestClient, unique_user: TestUser, price_source):
    calls, state = price_source
    pasta = create_food(unique_user, named("Spaghetti"))
    oil = create_food(unique_user, named("Huile"))
    gone = create_food(unique_user, named("Sauce"))

    tracked = save_price(
        api_client, unique_user, pasta, "migros", 2.0, size=750, sizeUnit="g",
        source="swissgroceries", externalId=SPAGHETTI["id"],
    )  # fmt: skip
    manual = save_price(api_client, unique_user, oil, "migros", 5.5, size=1, sizeUnit="l")
    save_price(api_client, unique_user, gone, "coop", 3, source="swissgroceries", externalId="discontinued")

    response = api_client.post(f"{PRICES}/refresh", headers=unique_user.token)
    assert response.status_code == 200, response.text
    assert response.json() == {"available": True, "updated": 1, "unchanged": 0, "failed": 1}
    # only the prices that came from the source are read again
    assert sorted(arguments["id"] for _, arguments in calls) == [SPAGHETTI["id"], "discontinued"]

    after = api_client.get(f"{PRICES}/{tracked['id']}", headers=unique_user.token).json()
    assert (after["price"], after["regularPrice"], after["promotion"]) == (1.6, 2.0, "20%")
    assert after["promotionEndsOn"] == "2099-01-01"
    assert api_client.get(f"{PRICES}/{manual['id']}", headers=unique_user.token).json()["price"] == 5.5

    again = api_client.post(f"{PRICES}/refresh", headers=unique_user.token).json()
    assert (again["updated"], again["unchanged"], again["failed"]) == (0, 1, 1)

    state["fail"] = True
    down = api_client.post(f"{PRICES}/refresh", headers=unique_user.token).json()
    assert down == {"available": False, "updated": 0, "unchanged": 0, "failed": 2}
    # a source that does not answer changes nothing
    assert api_client.get(f"{PRICES}/{tracked['id']}", headers=unique_user.token).json()["price"] == 1.6


def test_budget_of_a_shopping_plan(api_client: TestClient, unique_user: TestUser):
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    pasta = create_food(unique_user, named("Spaghetti"))
    tomato = create_food(unique_user, named("Tomates"))
    onion = create_food(unique_user, named("Oignon"))
    basil = create_food(unique_user, named("Basilic"))
    recipe = create_recipe(
        unique_user,
        servings=4,
        ingredients=[
            (400, gram, pasta, ""),
            (600, gram, tomato, ""),
            (2, None, onion, ""),
            (1, None, basil, ""),
            (1, None, None, "sel"),
        ],
    )
    plan = recipes_plan(api_client, unique_user, [(recipe, 2)], useStock=True, usePackaging=False)

    # 800 g of pasta: two packs of 500 g at Migros, one pack of 1 kg at Coop
    save_price(api_client, unique_user, pasta, "migros", 1.2, size=500, sizeUnit="g")
    save_price(api_client, unique_user, pasta, "coop", 2.6, size=1, sizeUnit="kg", regularPrice=3.2, promotion="-20%")
    # tomatoes by weight at Migros only
    save_price(api_client, unique_user, tomato, "migros", 3.5, size=1, sizeUnit="kg", byWeight=True)
    # onions priced by the kilogram cannot price "4 onions"
    save_price(api_client, unique_user, onion, "migros", 2.2, size=1, sizeUnit="kg")

    response = api_client.get(f"{PLANS}/{plan['id']}/budget", headers=unique_user.token)
    assert response.status_code == 200, response.text
    budget = response.json()

    assert (budget["currency"], budget["lineCount"]) == ("CHF", 5)
    lines = {line["display"].split()[-1]: line for line in budget["lines"]}
    by_food = {line["foodId"]: line for line in budget["lines"]}

    pasta_line = by_food[str(pasta.id)]
    assert [(offer["store"], offer["cost"], offer["packs"]) for offer in pasta_line["offers"]] == [
        ("migros", 2.4, 2),
        ("coop", 2.6, 1),
    ]
    assert pasta_line["offers"][1]["onPromotion"] is True
    assert by_food[str(tomato.id)]["offers"] == [
        {"store": "migros", "cost": 4.2, "usedCost": 4.2, "packs": None, "label": None, "onPromotion": False}
    ]
    assert by_food[str(onion.id)]["reason"] == "UNIT_MISMATCH"
    assert by_food[str(basil.id)]["reason"] == "NO_PRICE"
    assert lines["sel"]["reason"] == "NO_FOOD"

    # Migros prices two lines, Coop one: the shop that covers more lines comes first
    assert [
        (total["store"], total["total"], total["pricedLines"], total["missingLines"]) for total in budget["stores"]
    ] == [
        ("migros", 6.6, 2, 3),
        ("coop", 2.6, 1, 4),
    ]
    assert budget["stores"][1]["promotions"] == 1
    assert (budget["best"]["store"], budget["best"]["total"], budget["best"]["pricedLines"]) == ("*", 6.6, 2)

    # what is in stock is not bought, so it is not in the budget
    add_stock(api_client, unique_user, pasta, 800, gram)
    budget = api_client.get(f"{PLANS}/{plan['id']}/budget", headers=unique_user.token).json()
    assert budget["lineCount"] == 4
    assert str(pasta.id) not in [line["foodId"] for line in budget["lines"]]
    assert [(total["store"], total["total"]) for total in budget["stores"]] == [("migros", 4.2)]

    assert api_client.get(f"{PLANS}/{plan['id']}/budget", headers=unique_user.token).status_code == 200
    missing = api_client.get(f"{PLANS}/00000000-0000-4000-8000-000000000000/budget", headers=unique_user.token)
    assert missing.status_code == 404


def test_cost_of_a_recipe(api_client: TestClient, unique_user: TestUser):
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    pasta = create_food(unique_user, named("Spaghetti"))
    cheese = create_food(unique_user, named("Parmesan"))
    pepper = create_food(unique_user, named("Poivre"))
    recipe = create_recipe(
        unique_user,
        servings=4,
        ingredients=[(400, gram, pasta, ""), (80, gram, cheese, ""), (0, None, pepper, ""), (2, None, None, "œufs")],
    )
    save_price(api_client, unique_user, pasta, "migros", 1.2, size=500, sizeUnit="g")
    save_price(api_client, unique_user, pasta, "coop", 2.0, size=1, sizeUnit="kg")
    ends = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    # the promotion ended yesterday: the regular price counts
    save_price(
        api_client, unique_user, cheese, "coop", 4.0, size=200, sizeUnit="g",
        regularPrice=5.0, promotion="-20%", promotionEndsOn=ends,
    )  # fmt: skip

    response = api_client.get(f"{PRICES}/recipes/{recipe.id}", headers=unique_user.token)
    assert response.status_code == 200, response.text
    cost = response.json()

    # pasta: 400 g at 2.00 the kilogram (Coop) = 0.80; cheese: 80 g of 200 g at 5.00 = 2.00
    assert (cost["total"], cost["perServing"], cost["servings"]) == (2.8, 0.7, 4)
    # the pepper has no quantity and is not counted; the eggs have no food
    assert (cost["pricedIngredients"], cost["ingredientCount"]) == (2, 3)
    by_display = {entry["display"]: entry for entry in cost["ingredients"]}
    assert (by_display[pasta.name]["cost"], by_display[pasta.name]["store"]) == (0.8, "coop")
    assert by_display["œufs"]["reason"] == "NO_FOOD"

    unpriced = create_recipe(unique_user, servings=2, ingredients=[(1, None, pepper, "")])
    empty = api_client.get(f"{PRICES}/recipes/{unpriced.id}", headers=unique_user.token).json()
    assert (empty["total"], empty["perServing"], empty["pricedIngredients"]) == (0, None, 0)

    missing = api_client.get(f"{PRICES}/recipes/00000000-0000-4000-8000-000000000000", headers=unique_user.token)
    assert missing.status_code == 404
