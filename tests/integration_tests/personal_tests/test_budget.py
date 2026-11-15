from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from mealie.services.personal.price_source import PriceSource, PriceSourceUnavailable
from tests.utils import api_routes
from tests.utils.fixture_schemas import TestUser

from .helpers import BASE, create_food, create_recipe, create_unit, purge_orphans
from .test_prices import named, save_price
from .test_shopping_plans import recipes_plan

BUDGET = f"{BASE}/budget"
EXPENSES = f"{BUDGET}/expenses"
PLANS = f"{BASE}/shopping-plans"
PRICES = f"{BASE}/prices"


def product(chain: str, product_id: str, name: str, price: float, size: float, unit: str) -> dict:
    return {
        "chain": chain,
        "id": product_id,
        "name": name,
        "size": {"value": size, "unit": unit},
        "price": {"current": price, "currency": "CHF"},
    }


@pytest.fixture()
def shops(monkeypatch: pytest.MonkeyPatch):
    """Replaces the network call of the price service: it answers each search text with the products given."""
    calls: list[tuple[str, dict]] = []
    state: dict = {"fail": False, "answers": {}, "errors": []}

    def fake_call(self, tool: str, arguments: dict):
        calls.append((tool, arguments))
        if state["fail"]:
            raise PriceSourceUnavailable()
        answer = state["answers"].get(arguments["query"], {})
        return {
            "byChain": {chain: answer.get(chain, []) for chain in arguments["chains"]},
            "errors": [error for error in state["errors"] if error["chain"] in arguments["chains"]],
        }

    monkeypatch.setenv("PE_PRICE_SOURCE_URL", "http://price-bridge:8080")
    monkeypatch.setattr(PriceSource, "_call", fake_call)
    return calls, state


def add_expense(api_client: TestClient, user: TestUser, spent_on: date, store: str, amount: float, **fields) -> dict:
    payload = {"spentOn": spent_on.isoformat(), "store": store, "amount": amount, **fields}
    response = api_client.post(EXPENSES, json=payload, headers=user.token)
    assert response.status_code == 201, response.text
    return response.json()


def prices_of(api_client: TestClient, user: TestUser, *foods) -> list[tuple[str, float]]:
    """The stored prices of some foods, as (shop, price). The user of a test module keeps what earlier tests stored."""
    wanted = {str(food.id) for food in foods}
    listed = api_client.get(PRICES, params={"perPage": -1}, headers=user.token).json()["items"]
    return sorted((price["store"], price["price"]) for price in listed if price["foodId"] in wanted)


def month_start(months_ago: int) -> date:
    first = datetime.now(UTC).date().replace(day=1)
    index = first.year * 12 + first.month - 1 - months_ago
    return date(index // 12, index % 12 + 1, 1)


def test_expense_crud(api_client: TestClient, unique_user: TestUser, h2_user: TestUser):
    day = month_start(0)
    expense = add_expense(api_client, unique_user, day, " Migros ", 84.456, note="Courses de la semaine")
    assert (expense["store"], expense["amount"], expense["currency"]) == ("migros", 84.46, "CHF")
    assert (expense["spentOn"], expense["note"], expense["planId"]) == (day.isoformat(), "Courses de la semaine", None)

    changed = api_client.put(
        f"{EXPENSES}/{expense['id']}",
        json={"spentOn": day.isoformat(), "store": "marché", "amount": 12},
        headers=unique_user.token,
    )
    assert changed.status_code == 200, changed.text
    assert (changed.json()["store"], changed.json()["amount"], changed.json()["note"]) == ("marché", 12, None)

    listed = api_client.get(EXPENSES, params={"perPage": -1}, headers=unique_user.token).json()["items"]
    assert [item["id"] for item in listed] == [expense["id"]]

    # an expense belongs to one household
    assert api_client.get(f"{EXPENSES}/{expense['id']}", headers=h2_user.token).status_code == 404
    assert api_client.get(EXPENSES, params={"perPage": -1}, headers=h2_user.token).json()["items"] == []
    assert api_client.get(f"{BUDGET}/summary", headers=h2_user.token).json()["expenseCount"] == 0

    for payload in (
        {"spentOn": day.isoformat(), "store": "migros", "amount": 0},
        {"spentOn": day.isoformat(), "store": "  ", "amount": 5},
        {"spentOn": "hier", "store": "migros", "amount": 5},
    ):
        assert api_client.post(EXPENSES, json=payload, headers=unique_user.token).status_code == 422, payload

    future = (datetime.now(UTC).date() + timedelta(days=3)).isoformat()
    refused = api_client.post(
        EXPENSES, json={"spentOn": future, "store": "migros", "amount": 5}, headers=unique_user.token
    )
    assert refused.status_code == 400
    assert refused.json()["detail"]["exception"] == "EXPENSE_IN_FUTURE"

    deleted = api_client.delete(f"{EXPENSES}/{expense['id']}", headers=unique_user.token)
    assert deleted.status_code == 200
    assert api_client.get(f"{EXPENSES}/{expense['id']}", headers=unique_user.token).status_code == 404


def test_summary_by_month_and_by_shop(api_client: TestClient, unique_user: TestUser):
    empty = api_client.get(f"{BUDGET}/summary", headers=unique_user.token).json()
    assert (len(empty["months"]), empty["total"], empty["averageMonth"], empty["remaining"]) == (12, 0, None, None)

    add_expense(api_client, unique_user, month_start(3), "coop", 100)
    add_expense(api_client, unique_user, month_start(1), "migros", 50, estimatedAmount=40)
    add_expense(api_client, unique_user, month_start(1) + timedelta(days=9), "coop", 30)
    add_expense(api_client, unique_user, month_start(0), "migros", 70.5, estimatedAmount=75)
    # too old for the period that the summary covers
    add_expense(api_client, unique_user, month_start(30), "migros", 999)

    settings = api_client.put(f"{BUDGET}/settings", json={"monthlyTarget": 500}, headers=unique_user.token)
    assert settings.status_code == 200, settings.text
    assert settings.json()["monthlyTarget"] == 500

    response = api_client.get(f"{BUDGET}/summary", params={"months": 6}, headers=unique_user.token)
    assert response.status_code == 200, response.text
    summary = response.json()

    assert [month["month"] for month in summary["months"]] == [
        month_start(offset).strftime("%Y-%m") for offset in (5, 4, 3, 2, 1, 0)
    ]
    assert [month["total"] for month in summary["months"]] == [0, 0, 100, 0, 80, 70.5]
    assert summary["months"][4]["stores"] == [
        {"store": "migros", "total": 50, "count": 1},
        {"store": "coop", "total": 30, "count": 1},
    ]
    assert (summary["current"]["month"], summary["current"]["total"]) == (month_start(0).strftime("%Y-%m"), 70.5)
    assert (summary["total"], summary["expenseCount"]) == (250.5, 4)
    assert [(store["store"], store["total"], store["count"]) for store in summary["stores"]] == [
        ("coop", 130, 2),
        ("migros", 120.5, 2),
    ]

    # the target of the month, and the mean of the complete months since the first expense: 100, 0 and 80
    assert (summary["monthlyTarget"], summary["remaining"], summary["averageMonth"]) == (500, 429.5, 60)
    # two expenses have an estimate: 115 expected, 120.50 paid
    assert summary["estimateCheck"] == {"count": 2, "estimated": 115, "paid": 120.5}

    # the settings keep one row: a second write changes it
    api_client.put(f"{BUDGET}/settings", json={"monthlyTarget": 50, "usualStore": " Coop "}, headers=unique_user.token)
    summary = api_client.get(f"{BUDGET}/summary", headers=unique_user.token).json()
    assert (summary["monthlyTarget"], summary["usualStore"], summary["remaining"]) == (50, "coop", -20.5)
    assert len(unique_user.repos.pe_budget_settings.get_all()) == 1

    assert api_client.get(f"{BUDGET}/summary", params={"months": 0}, headers=unique_user.token).status_code == 422


def test_the_shopping_of_a_plan_becomes_an_expense(api_client: TestClient, unique_user: TestUser):
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    pasta = create_food(unique_user, named("Spaghetti"))
    recipe = create_recipe(unique_user, ingredients=[(400, gram, pasta, "")])
    plan = recipes_plan(api_client, unique_user, [(recipe, 2)], usePackaging=False)
    save_price(api_client, unique_user, pasta, "migros", 1.2, size=500, sizeUnit="g")

    # without an amount, the estimate of the application for the shop is the expense
    response = api_client.post(f"{PLANS}/{plan['id']}/expense", json={"store": "Migros"}, headers=unique_user.token)
    assert response.status_code == 201, response.text
    estimated = response.json()
    assert (estimated["store"], estimated["amount"], estimated["estimatedAmount"]) == ("migros", 2.4, 2.4)
    assert (estimated["planId"], estimated["planName"]) == (plan["id"], "Courses")
    assert estimated["spentOn"] == datetime.now(UTC).date().isoformat()

    # the amount of the receipt stays beside the estimate
    paid = api_client.post(
        f"{PLANS}/{plan['id']}/expense",
        json={"store": "migros", "amount": 3.1, "spentOn": month_start(0).isoformat()},
        headers=unique_user.token,
    ).json()
    assert (paid["amount"], paid["estimatedAmount"], paid["spentOn"]) == (3.1, 2.4, month_start(0).isoformat())

    # a shop without a price has no estimate: the person gives the amount
    refused = api_client.post(f"{PLANS}/{plan['id']}/expense", json={"store": "marché"}, headers=unique_user.token)
    assert refused.status_code == 400
    assert refused.json()["detail"]["exception"] == "EXPENSE_AMOUNT_REQUIRED"
    market = api_client.post(
        f"{PLANS}/{plan['id']}/expense", json={"store": "marché", "amount": 9}, headers=unique_user.token
    ).json()
    assert (market["amount"], market["estimatedAmount"]) == (9, None)

    unknown = "00000000-0000-4000-8000-000000000000"
    missing = api_client.post(f"{PLANS}/{unknown}/expense", json={"store": "migros"}, headers=unique_user.token)
    assert missing.status_code == 404

    # the expense is a fact: it stays when the plan is deleted, with the name of the plan
    assert api_client.delete(f"{PLANS}/{plan['id']}", headers=unique_user.token).status_code == 200
    purge_orphans(unique_user)
    unique_user.repos.session.expire_all()
    kept = api_client.get(f"{EXPENSES}/{paid['id']}", headers=unique_user.token).json()
    assert (kept["planId"], kept["planName"], kept["amount"]) == (None, "Courses", 3.1)


def test_store_match_proposes_the_products_of_each_shop(api_client: TestClient, unique_user: TestUser, shops):
    calls, state = shops
    liter = create_unit(unique_user, standard_quantity=1, standard_unit="liter")
    milk = create_food(unique_user, named("Lait"))
    onion = create_food(unique_user, named("Oignon"))
    recipe = create_recipe(
        unique_user, ingredients=[(1, liter, milk, ""), (2, None, onion, ""), (1, None, None, "sel")]
    )
    plan = recipes_plan(api_client, unique_user, [(recipe, 1)], usePackaging=False)

    state["answers"] = {
        "Milch": {
            "migros": [
                product("migros", "m1", "Milchschokolade", 1.9, 100, "g"),
                product("migros", "m2", "Bio Bergmilch", 1.65, 500, "g"),
                product("migros", "m3", "M-Classic Milch UHT", 1.4, 1, "l"),
            ],
            "coop": [
                product("coop", "c1", "Milch Drink", 1.55, 1, "l"),
                product("coop", "c2", "Butter", 3.2, 250, "g"),
                product("coop", "c3", "Milch UHT 6x1l", 9.9, 6, "l"),
            ],
        },
        "Zwiebeln": {
            "migros": [product("migros", "m9", "Zwiebeln gelb", 2.2, 1, "kg")],
            "aldi": [product("aldi", "a9", "Zwiebeln, Classic", 0.49, 1.5, "l")],
        },
    }
    state["errors"] = [{"chain": "lidl", "code": "unavailable"}]

    response = api_client.post(f"{PLANS}/{plan['id']}/store-match", json={}, headers=unique_user.token)
    assert response.status_code == 200, response.text
    match = response.json()
    assert (match["available"], match["searchedLines"]) == (True, 2)
    lines = {line["foodId"] or line["display"].split()[-1]: line for line in match["lines"]}
    assert len(lines) == 3

    # the shops are searched with their own word, and a request carries nothing else
    assert sorted(arguments["query"] for _, arguments in calls) == ["Milch", "Zwiebeln"]
    for tool, arguments in calls:
        assert tool == "search_products"
        assert set(arguments) == {"query", "chains", "limit"}
        assert arguments["chains"] == ["coop", "migros", "aldi", "lidl"]

    milk_line = lines[str(milk.id)]
    assert (milk_line["query"], milk_line["translated"], milk_line["reason"]) == ("Milch", True, None)
    stores = {store["store"]: store for store in milk_line["stores"]}
    assert list(stores) == ["coop", "migros", "aldi", "lidl"]

    # the milk comes first, whatever the order of the shop, and the milk chocolate is not proposed
    migros = stores["migros"]["candidates"]
    assert [candidate["offer"]["name"] for candidate in migros] == [
        "M-Classic Milch UHT",
        "Bio Bergmilch",
    ]
    # only the product that is the food for sure is selected for the person
    assert [candidate["confident"] for candidate in migros] == [True, False]
    assert (migros[0]["cost"], migros[0]["packs"], migros[0]["fits"], migros[0]["score"]) == (1.4, 1, True, 1)
    # a pack in grams cannot measure a liter of milk
    assert (migros[1]["fits"], migros[1]["cost"]) == (False, 1.65)

    # the butter is off the subject: it is not proposed
    coop = stores["coop"]["candidates"]
    assert [candidate["offer"]["name"] for candidate in coop] == ["Milch Drink", "Milch UHT 6x1l"]
    # a pack of six costs several times the other milks: the person must choose it
    assert [(candidate["cost"], candidate["confident"]) for candidate in coop] == [(1.55, True), (9.9, False)]
    # Aldi answered with nothing; Lidl did not answer
    assert (stores["aldi"]["searched"], stores["aldi"]["failed"], stores["aldi"]["candidates"]) == (True, False, [])
    assert (stores["lidl"]["searched"], stores["lidl"]["failed"]) == (True, True)

    # 2 onions against a pack of 1 kg: the usual weight of an onion gives one pack
    onion_stores = {store["store"]: store for store in lines[str(onion.id)]["stores"]}
    assert lines[str(onion.id)]["query"] == "Zwiebeln"
    (onions,) = onion_stores["migros"]["candidates"]
    assert (onions["cost"], onions["packs"], onions["fits"], onions["confident"]) == (2.2, 1, True, True)
    # onions are counted in pieces: a bottle is a drink with the same name, the person must choose it
    (bottle,) = onion_stores["aldi"]["candidates"]
    assert (bottle["score"], bottle["fits"], bottle["confident"]) == (1, False, False)

    # free text has no food to search for
    assert lines["sel"]["reason"] == "NO_FOOD" and lines["sel"]["stores"] == []

    # nothing is stored until the person keeps the products
    assert prices_of(api_client, unique_user, milk, onion) == []
    kept = api_client.post(
        f"{PRICES}/bulk",
        json=[
            {
                "foodId": str(milk.id),
                "store": candidate["offer"]["store"],
                "label": candidate["offer"]["name"],
                "price": candidate["offer"]["price"],
                "size": candidate["offer"]["size"],
                "sizeUnit": candidate["offer"]["sizeUnit"],
                "source": "swissgroceries",
                "externalId": candidate["offer"]["externalId"],
            }
            for candidate in (migros[0], stores["coop"]["candidates"][0])
        ],
        headers=unique_user.token,
    )
    assert kept.status_code == 201, kept.text
    assert sorted((price["store"], price["price"]) for price in kept.json()) == [("coop", 1.55), ("migros", 1.4)]

    # the plan now compares the two shops on the whole shopping
    budget = api_client.get(f"{PLANS}/{plan['id']}/budget", headers=unique_user.token).json()
    assert [(total["store"], total["basketTotal"]) for total in budget["stores"]] == [("migros", 1.4), ("coop", 1.55)]
    assert budget["recommendedStore"] == "migros"

    # a shop that has a price is not searched again
    calls.clear()
    again = api_client.post(
        f"{PLANS}/{plan['id']}/store-match", json={"keys": [milk_line["key"]]}, headers=unique_user.token
    ).json()
    assert [line["foodId"] for line in again["lines"]] == [str(milk.id)]
    assert [arguments["chains"] for _, arguments in calls] == [["aldi", "lidl"]]
    stores = {store["store"]: store for store in again["lines"][0]["stores"]}
    assert (stores["migros"]["hasStored"], stores["migros"]["storedPrice"], stores["migros"]["searched"]) == (
        True,
        1.4,
        False,
    )
    assert stores["migros"]["storedLabel"] == "M-Classic Milch UHT"

    # ... unless the person asks for it, or types another search text
    calls.clear()
    api_client.post(
        f"{PLANS}/{plan['id']}/store-match",
        json={"keys": [milk_line["key"]], "refresh": True},
        headers=unique_user.token,
    )
    typed = api_client.post(
        f"{PLANS}/{plan['id']}/store-match",
        json={"keys": [milk_line["key"]], "queries": {milk_line["key"]: "  Bio   Milch "}},
        headers=unique_user.token,
    ).json()
    assert [(arguments["query"], len(arguments["chains"])) for _, arguments in calls] == [
        ("Milch", 4),
        ("Bio Milch", 4),
    ]
    assert (typed["lines"][0]["query"], typed["lines"][0]["translated"]) == ("Bio Milch", False)

    unknown = "00000000-0000-4000-8000-000000000000"
    assert api_client.post(f"{PLANS}/{unknown}/store-match", json={}, headers=unique_user.token).status_code == 404


def test_store_match_without_an_answer(api_client: TestClient, unique_user: TestUser, shops, monkeypatch):
    calls, state = shops
    food = create_food(unique_user, named("Beurre"))
    recipe = create_recipe(unique_user, ingredients=[(1, None, food, "")])
    plan = recipes_plan(api_client, unique_user, [(recipe, 1)])

    # the price service does not answer: the plan stays usable
    state["fail"] = True
    down = api_client.post(f"{PLANS}/{plan['id']}/store-match", json={}, headers=unique_user.token)
    assert down.status_code == 200, down.text
    assert (down.json()["available"], down.json()["searchedLines"]) == (False, 0)
    assert down.json()["lines"][0]["query"] == "Butter"

    # no price service is configured: nothing is asked
    calls.clear()
    monkeypatch.delenv("PE_PRICE_SOURCE_URL")
    off = api_client.post(f"{PLANS}/{plan['id']}/store-match", json={}, headers=unique_user.token).json()
    assert (off["available"], len(off["lines"]), calls) == (False, 1, [])


def test_bulk_prices_are_checked(api_client: TestClient, unique_user: TestUser):
    food = create_food(unique_user, named("Riz"))
    unknown = "00000000-0000-4000-8000-000000000000"

    # the same food and shop twice: the second price replaces the first
    twice = api_client.post(
        f"{PRICES}/bulk",
        json=[
            {"foodId": str(food.id), "store": "migros", "price": 2},
            {"foodId": str(food.id), "store": "migros", "price": 3},
        ],
        headers=unique_user.token,
    )
    assert twice.status_code == 201, twice.text
    assert prices_of(api_client, unique_user, food) == [("migros", 3)]

    missing = api_client.post(
        f"{PRICES}/bulk", json=[{"foodId": unknown, "store": "migros", "price": 2}], headers=unique_user.token
    )
    assert missing.status_code == 404
    invalid = api_client.post(
        f"{PRICES}/bulk", json=[{"foodId": str(food.id), "store": "migros", "price": 0}], headers=unique_user.token
    )
    assert invalid.status_code == 422


def test_cost_of_the_meals_and_of_the_recipes(api_client: TestClient, unique_user: TestUser):
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    pasta = create_food(unique_user, named("Spaghetti"))
    egg = create_food(unique_user, named("Œuf"))
    carbonara = create_recipe(
        unique_user, "Carbonara", servings=4, ingredients=[(400, gram, pasta, ""), (4, None, egg, "")]
    )
    unpriced = create_recipe(unique_user, "Salade", servings=2, ingredients=[(1, None, create_food(unique_user), "")])

    save_price(api_client, unique_user, pasta, "migros", 1.2, size=500, sizeUnit="g")
    save_price(api_client, unique_user, pasta, "coop", 2.0, size=1, sizeUnit="kg")
    # 4 eggs of 60 g against eggs sold by weight: 240 g of 600 g
    save_price(api_client, unique_user, egg, "coop", 6.0, size=600, sizeUnit="g")

    start = date(2031, 3, 3)
    for offset, recipe, scale in ((0, carbonara, 1), (1, unpriced, 1), (2, carbonara, 2), (20, carbonara, 1)):
        entry = {
            "date": (start + timedelta(days=offset)).isoformat(),
            "entryType": "dinner",
            "recipeId": str(recipe.id),
            "recipeScale": scale,
        }
        response = api_client.post(api_routes.households_mealplans, json=entry, headers=unique_user.token)
        assert response.status_code == 201, response.text

    # an earlier test of this module may have set a usual shop
    api_client.put(f"{BUDGET}/settings", json={}, headers=unique_user.token)
    week = {"dateFrom": start.isoformat(), "dateTo": (start + timedelta(days=6)).isoformat()}
    response = api_client.get(f"{BUDGET}/meals", params=week, headers=unique_user.token)
    assert response.status_code == 200, response.text
    meals = response.json()

    # without a shop, each food counts at its cheapest price: pasta 0.80 at Coop, eggs 2.40 at Coop
    assert (meals["store"], meals["total"], meals["pricedMeals"], len(meals["meals"])) == (None, 9.6, 2, 3)
    first, salad, double = meals["meals"]
    assert (first["recipeName"], first["total"], first["perServing"], first["servings"]) == ("Carbonara", 3.2, 0.8, 4)
    assert (first["pricedIngredients"], first["ingredientCount"]) == (2, 2)
    assert (double["total"], double["perServing"], double["servings"]) == (6.4, 0.8, 8)
    # a recipe without a price has no cost, and is not counted as zero
    assert (salad["recipeName"], salad["total"], salad["perServing"]) == ("Salade", None, None)

    # at Migros only the pasta has a price: half of the ingredients, 0.96
    migros = api_client.get(f"{BUDGET}/meals", params={**week, "store": "migros"}, headers=unique_user.token).json()
    assert (migros["store"], migros["total"], migros["meals"][0]["total"]) == ("migros", 2.88, 0.96)

    # the usual shop of the household prices the meals when the request names no shop
    api_client.put(f"{BUDGET}/settings", json={"usualStore": "migros"}, headers=unique_user.token)
    usual = api_client.get(f"{BUDGET}/meals", params=week, headers=unique_user.token).json()
    assert (usual["store"], usual["total"]) == ("migros", 2.88)
    every = api_client.get(f"{BUDGET}/meals", params={**week, "store": ""}, headers=unique_user.token).json()
    assert (every["store"], every["total"]) == (None, 9.6)

    recipes = api_client.get(f"{BUDGET}/recipes", params={"store": ""}, headers=unique_user.token).json()
    mine = {str(carbonara.id): carbonara, str(unpriced.id): unpriced}
    listed = [recipe for recipe in recipes["recipes"] if recipe["recipeId"] in mine]
    # the recipes with a cost come first
    assert [(recipe["recipeName"], recipe["perServing"]) for recipe in listed] == [("Carbonara", 0.8), ("Salade", None)]
    assert listed[0]["recipeSlug"] == carbonara.slug
    assert recipes["pricedCount"] == sum(1 for recipe in recipes["recipes"] if recipe["total"] is not None) >= 1

    backwards = {"dateFrom": week["dateTo"], "dateTo": week["dateFrom"]}
    refused = api_client.get(f"{BUDGET}/meals", params=backwards, headers=unique_user.token)
    assert (refused.status_code, refused.json()["detail"]["exception"]) == (400, "DATE_RANGE_INVALID")
    long = {"dateFrom": "2031-01-01", "dateTo": "2031-12-31"}
    refused = api_client.get(f"{BUDGET}/meals", params=long, headers=unique_user.token)
    assert (refused.status_code, refused.json()["detail"]["exception"]) == (400, "DATE_RANGE_TOO_LONG")
