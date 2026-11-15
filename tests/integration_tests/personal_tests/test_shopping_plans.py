from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.utils import api_routes
from tests.utils.fixture_schemas import TestUser

from .helpers import BASE, create_food, create_person, create_recipe, create_unit, restriction_ids
from .scenario import build_burger_scenario

PLANS = f"{BASE}/shopping-plans"


def create_plan(api_client: TestClient, user: TestUser, **payload) -> dict:
    response = api_client.post(PLANS, json={"name": "Courses", **payload}, headers=user.token)
    assert response.status_code == 201, response.text
    return response.json()


def recipes_plan(api_client: TestClient, user: TestUser, recipes: list, **payload) -> dict:
    entries = [{"recipeId": str(recipe.id), "scale": scale} for recipe, scale in recipes]
    return create_plan(api_client, user, sourceType="RECIPES", recipes=entries, **payload)


def apply_plan(api_client: TestClient, user: TestUser, plan_id: str, **payload) -> dict:
    response = api_client.post(f"{PLANS}/{plan_id}/apply", json=payload, headers=user.token)
    assert response.status_code == 200, response.text
    return response.json()


def preview_plan(api_client: TestClient, user: TestUser, plan_id: str) -> dict:
    response = api_client.get(f"{PLANS}/{plan_id}/preview", headers=user.token)
    assert response.status_code == 200, response.text
    return response.json()


def list_items(api_client: TestClient, user: TestUser, list_id: str) -> list[dict]:
    response = api_client.get(api_routes.households_shopping_lists_item_id(list_id), headers=user.token)
    assert response.status_code == 200, response.text
    return response.json()["listItems"]


def item_for(items: list[dict], food) -> dict:
    matches = [item for item in items if item["foodId"] == str(food.id)]
    assert len(matches) == 1, matches
    return matches[0]


def update_item(api_client: TestClient, user: TestUser, item: dict, **changes) -> None:
    response = api_client.put(
        api_routes.households_shopping_items_item_id(item["id"]), json={**item, **changes}, headers=user.token
    )
    assert response.status_code == 200, response.text


def add_stock(api_client: TestClient, user: TestUser, food, quantity: float, unit=None, confirmed=True) -> dict:
    payload = {
        "foodId": str(food.id),
        "quantity": quantity,
        "unitId": str(unit.id) if unit else None,
        "confirmedUsable": confirmed,
    }
    response = api_client.post(f"{BASE}/pantry", json=payload, headers=user.token)
    assert response.status_code == 201, response.text
    return response.json()


def line_for(lines: list[dict], food) -> dict:
    return next(line for line in lines if line["foodId"] == str(food.id))


# ----------------------------------------------------------------------------------------------------------------
# The reference scenario


def test_burger_event_shopping_list(api_client: TestClient, unique_user: TestUser):
    scenario = build_burger_scenario(api_client, unique_user)
    plan = create_plan(api_client, unique_user, sourceType="EVENT", eventId=scenario.event["id"])

    result = apply_plan(api_client, unique_user, plan["id"])
    assert result["issues"] == []
    items = list_items(api_client, unique_user, result["shoppingListId"])
    foods = scenario.foods

    # both variants are on the list, and the ingredients they share are grouped into one item
    assert len(items) == 6
    assert item_for(items, foods["bun"])["quantity"] == 7
    assert item_for(items, foods["cheddar"])["quantity"] == 7
    assert item_for(items, foods["tomato"])["quantity"] == 350
    assert item_for(items, foods["salad"])["quantity"] == 175
    assert item_for(items, foods["beef"])["quantity"] == 0.9
    assert item_for(items, foods["veggie_patty"])["quantity"] == 1

    # each item keeps the recipes it comes from
    bun_recipes = {ref["recipeId"] for ref in item_for(items, foods["bun"])["recipeReferences"]}
    assert bun_recipes == {str(scenario.beef_burger.id), str(scenario.veggie_burger.id)}
    beef_recipes = {ref["recipeId"] for ref in item_for(items, foods["beef"])["recipeReferences"]}
    assert beef_recipes == {str(scenario.beef_burger.id)}

    # every line is flagged for the gluten restriction of the cook; none is cleared without a person
    for line in result["lines"]:
        gluten_checks = [check for check in line["checks"] if check["restrictionKey"] == "gluten"]
        assert len(gluten_checks) == 1, line
        assert gluten_checks[0]["status"] == "UNVERIFIED"
    assert line_for(result["lines"], foods["bun"])["checks"][0]["code"] == "FREE_CLAIM"
    assert line_for(result["lines"], foods["tomato"])["checks"][0]["code"] == "NO_DATA"

    # a second plan for the same event returns the first one
    again = create_plan(api_client, unique_user, sourceType="EVENT", eventId=scenario.event["id"])
    assert again["id"] == plan["id"]


def test_event_plan_reports_a_recipe_without_servings(api_client: TestClient, unique_user: TestUser):
    person = create_person(api_client, unique_user)
    recipe = create_recipe(unique_user, servings=0, ingredients=[(1, None, create_food(unique_user), "")])
    event = api_client.post(f"{BASE}/meal-events", json={"name": "Test"}, headers=unique_user.token).json()
    api_client.put(
        f"{BASE}/meal-events/{event['id']}/guests", json=[{"personId": person["id"]}], headers=unique_user.token
    )
    api_client.put(
        f"{BASE}/meal-events/{event['id']}/menu",
        json=[{"course": "MAIN", "variants": [{"recipeId": str(recipe.id)}]}],
        headers=unique_user.token,
    )
    plan = create_plan(api_client, unique_user, sourceType="EVENT", eventId=event["id"])

    preview = preview_plan(api_client, unique_user, plan["id"])
    assert preview["lines"] == []
    assert [issue["code"] for issue in preview["issues"]] == ["MISSING_SERVINGS"]


# ----------------------------------------------------------------------------------------------------------------
# Aggregation, stock and packs


def test_two_recipes_minus_confirmed_stock(api_client: TestClient, unique_user: TestUser):
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    tomato = create_food(unique_user)
    recipe_a = create_recipe(unique_user, ingredients=[(400, gram, tomato, "")])
    recipe_b = create_recipe(unique_user, ingredients=[(300, gram, tomato, "")])
    add_stock(api_client, unique_user, tomato, 200, gram, confirmed=True)

    plan = recipes_plan(api_client, unique_user, [(recipe_a, 1), (recipe_b, 1)])
    preview = preview_plan(api_client, unique_user, plan["id"])
    line = line_for(preview["lines"], tomato)

    assert line["quantityNeeded"] == 700
    assert line["quantityFromStock"] == 200
    assert line["quantityToBuy"] == 500
    assert [source["recipeName"] for source in line["sources"]] == [recipe_a.name, recipe_b.name]

    result = apply_plan(api_client, unique_user, plan["id"])
    assert item_for(list_items(api_client, unique_user, result["shoppingListId"]), tomato)["quantity"] == 500


def test_unconfirmed_stock_is_not_subtracted(api_client: TestClient, unique_user: TestUser):
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    tomato = create_food(unique_user)
    recipe = create_recipe(unique_user, ingredients=[(400, gram, tomato, "")])
    add_stock(api_client, unique_user, tomato, 200, gram, confirmed=False)

    plan = recipes_plan(api_client, unique_user, [(recipe, 1)])
    line = line_for(preview_plan(api_client, unique_user, plan["id"])["lines"], tomato)
    assert line["quantityFromStock"] == 0
    assert line["quantityToBuy"] == 400


def test_plan_can_ignore_the_stock(api_client: TestClient, unique_user: TestUser):
    tomato = create_food(unique_user)
    recipe = create_recipe(unique_user, ingredients=[(4, None, tomato, "")])
    add_stock(api_client, unique_user, tomato, 3)

    plan = recipes_plan(api_client, unique_user, [(recipe, 1)], useStock=False)
    assert line_for(preview_plan(api_client, unique_user, plan["id"])["lines"], tomato)["quantityToBuy"] == 4


def test_compatible_units_are_converted_and_scaled(api_client: TestClient, unique_user: TestUser):
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    kilogram = create_unit(unique_user, standard_quantity=1, standard_unit="kilogram")
    flour = create_food(unique_user)
    recipe_a = create_recipe(unique_user, ingredients=[(250, gram, flour, "")])
    recipe_b = create_recipe(unique_user, ingredients=[(0.5, kilogram, flour, "")])
    add_stock(api_client, unique_user, flour, 0.3, kilogram)

    plan = recipes_plan(api_client, unique_user, [(recipe_a, 3), (recipe_b, 1)])
    line = line_for(preview_plan(api_client, unique_user, plan["id"])["lines"], flour)

    assert line["unitId"] == str(kilogram.id)
    assert line["quantityNeeded"] == 1.25
    assert line["quantityFromStock"] == 0.3
    assert line["quantityToBuy"] == 0.95


def test_quantity_to_buy_is_rounded_to_packs(api_client: TestClient, unique_user: TestUser):
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    flour = create_food(unique_user)
    recipe = create_recipe(unique_user, ingredients=[(1250, gram, flour, "")])
    packaging = {"foodId": str(flour.id), "unitId": str(gram.id), "quantity": 1000, "label": "paquet 1 kg"}
    response = api_client.post(f"{BASE}/packagings", json=packaging, headers=unique_user.token)
    assert response.status_code == 201, response.text

    plan = recipes_plan(api_client, unique_user, [(recipe, 1)])
    line = line_for(preview_plan(api_client, unique_user, plan["id"])["lines"], flour)
    assert line["quantityNeeded"] == 1250
    assert line["quantityToBuy"] == 2000
    assert line["packs"] == 2
    assert line["packLabel"] == "paquet 1 kg"

    without = recipes_plan(api_client, unique_user, [(recipe, 1)], usePackaging=False)
    assert line_for(preview_plan(api_client, unique_user, without["id"])["lines"], flour)["quantityToBuy"] == 1250


def test_two_open_plans_do_not_count_on_the_same_stock(api_client: TestClient, unique_user: TestUser):
    rice = create_food(unique_user)
    recipe = create_recipe(unique_user, ingredients=[(3, None, rice, "")])
    add_stock(api_client, unique_user, rice, 4)

    first = recipes_plan(api_client, unique_user, [(recipe, 1)])
    apply_plan(api_client, unique_user, first["id"])
    second = recipes_plan(api_client, unique_user, [(recipe, 1)])

    line = line_for(preview_plan(api_client, unique_user, second["id"])["lines"], rice)
    assert line["quantityFromStock"] == 1
    assert line["quantityToBuy"] == 2


def test_week_of_the_meal_plan(api_client: TestClient, unique_user: TestUser):
    food = create_food(unique_user)
    recipe = create_recipe(unique_user, ingredients=[(2, None, food, "")])
    start = date(2031, 3, 3)
    for offset, scale in ((0, 1), (2, 2), (9, 5)):
        entry = {
            "date": (start + timedelta(days=offset)).isoformat(),
            "entryType": "dinner",
            "recipeId": str(recipe.id),
            "recipeScale": scale,
        }
        response = api_client.post(api_routes.households_mealplans, json=entry, headers=unique_user.token)
        assert response.status_code == 201, response.text

    plan = create_plan(
        api_client,
        unique_user,
        sourceType="MEALPLAN",
        dateFrom=start.isoformat(),
        dateTo=(start + timedelta(days=6)).isoformat(),
    )
    line = line_for(preview_plan(api_client, unique_user, plan["id"])["lines"], food)
    # the entry of the next week is outside the range
    assert line["quantityNeeded"] == 6
    assert len(line["sources"]) == 2


def test_owner_restrictions_are_checked_on_a_weekly_plan(api_client: TestClient, unique_user: TestUser):
    ids = restriction_ids(api_client, unique_user)
    create_person(
        api_client,
        unique_user,
        "Moi",
        isMe=True,
        restrictions=[
            {"restrictionId": ids["gluten"], "defaultScope": "ENTIRE_PREPARATION", "appliesWhenCooking": True}
        ],
    )
    wheat = create_food(unique_user, f"Farine de blé {uuid4().hex[:6]}")
    recipe = create_recipe(unique_user, ingredients=[(1, None, wheat, "")])

    plan = recipes_plan(api_client, unique_user, [(recipe, 1)])
    line = line_for(preview_plan(api_client, unique_user, plan["id"])["lines"], wheat)
    assert line["checks"] == [
        {"restrictionKey": "gluten", "status": "INCOMPATIBLE", "code": "RULE_MATCH", "term": "blé", "detail": None}
    ]


# ----------------------------------------------------------------------------------------------------------------
# Recalculation


def test_recalculation_keeps_purchases_and_manual_changes(api_client: TestClient, unique_user: TestUser):
    bought, adjusted, untouched = create_food(unique_user), create_food(unique_user), create_food(unique_user)
    recipe = create_recipe(
        unique_user,
        ingredients=[(4, None, bought, ""), (2, None, adjusted, ""), (1, None, untouched, "")],
    )
    plan = recipes_plan(api_client, unique_user, [(recipe, 1)])
    result = apply_plan(api_client, unique_user, plan["id"])
    list_id = result["shoppingListId"]
    assert (result["created"], result["updated"], result["deleted"]) == (3, 0, 0)

    items = list_items(api_client, unique_user, list_id)
    update_item(api_client, unique_user, item_for(items, bought), checked=True)
    update_item(api_client, unique_user, item_for(items, adjusted), quantity=5)
    manual = {"shoppingListId": list_id, "note": "éponges", "quantity": 1}
    assert (
        api_client.post(api_routes.households_shopping_items, json=manual, headers=unique_user.token).status_code == 201
    )

    # same plan again: nothing moves
    result = apply_plan(api_client, unique_user, plan["id"])
    assert (result["created"], result["updated"], result["deleted"]) == (0, 0, 0)
    items = list_items(api_client, unique_user, list_id)
    assert len(items) == 4
    assert item_for(items, bought)["checked"] is True
    assert item_for(items, bought)["quantity"] == 4
    assert item_for(items, adjusted)["quantity"] == 5
    assert any(item["note"] == "éponges" for item in items)

    # the plan doubles: only what is missing is added
    update = {
        "name": plan["name"],
        "sourceType": "RECIPES",
        "recipes": [{"recipeId": str(recipe.id), "scale": 2}],
    }
    assert api_client.put(f"{PLANS}/{plan['id']}", json=update, headers=unique_user.token).status_code == 200
    result = apply_plan(api_client, unique_user, plan["id"])
    items = list_items(api_client, unique_user, list_id)

    bought_items = [item for item in items if item["foodId"] == str(bought.id)]
    assert sorted((item["checked"], item["quantity"]) for item in bought_items) == [(False, 4), (True, 4)]
    # the manual +3 stays on top of the new need of 4
    assert item_for(items, adjusted)["quantity"] == 7
    assert item_for(items, untouched)["quantity"] == 2
    assert any(item["note"] == "éponges" for item in items)

    line = line_for(result["lines"], bought)
    assert line["purchasedQuantity"] == 4
    assert line["quantityToBuy"] == 8


def test_deleted_item_is_not_created_again(api_client: TestClient, unique_user: TestUser):
    food = create_food(unique_user)
    recipe = create_recipe(unique_user, ingredients=[(3, None, food, "")])
    plan = recipes_plan(api_client, unique_user, [(recipe, 1)])
    list_id = apply_plan(api_client, unique_user, plan["id"])["shoppingListId"]

    item = item_for(list_items(api_client, unique_user, list_id), food)
    deleted = api_client.delete(api_routes.households_shopping_items_item_id(item["id"]), headers=unique_user.token)
    assert deleted.status_code == 200

    result = apply_plan(api_client, unique_user, plan["id"])
    assert result["created"] == 0
    assert list_items(api_client, unique_user, list_id) == []
    assert line_for(result["lines"], food)["state"] == "DISMISSED"

    result = apply_plan(api_client, unique_user, plan["id"], restoreDismissed=True)
    assert result["created"] == 1
    assert item_for(list_items(api_client, unique_user, list_id), food)["quantity"] == 3


def test_recipe_removed_from_the_plan_removes_its_open_items(api_client: TestClient, unique_user: TestUser):
    kept, removed = create_food(unique_user), create_food(unique_user)
    recipe_a = create_recipe(unique_user, ingredients=[(1, None, kept, "")])
    recipe_b = create_recipe(unique_user, ingredients=[(1, None, removed, "")])
    plan = recipes_plan(api_client, unique_user, [(recipe_a, 1), (recipe_b, 1)])
    list_id = apply_plan(api_client, unique_user, plan["id"])["shoppingListId"]

    update = {"name": plan["name"], "sourceType": "RECIPES", "recipes": [{"recipeId": str(recipe_a.id), "scale": 1}]}
    api_client.put(f"{PLANS}/{plan['id']}", json=update, headers=unique_user.token)
    result = apply_plan(api_client, unique_user, plan["id"])

    assert result["deleted"] == 1
    items = list_items(api_client, unique_user, list_id)
    assert [item["foodId"] for item in items] == [str(kept.id)]
    lines = api_client.get(f"{PLANS}/{plan['id']}/lines", headers=unique_user.token).json()
    assert [line["foodId"] for line in lines] == [str(kept.id)]


def test_plan_merges_into_an_existing_item_and_keeps_its_quantity(api_client: TestClient, unique_user: TestUser):
    food = create_food(unique_user)
    recipe = create_recipe(unique_user, ingredients=[(2, None, food, "")])
    shopping_list = api_client.post(
        api_routes.households_shopping_lists, json={"name": "Semaine"}, headers=unique_user.token
    ).json()
    existing = {"shoppingListId": shopping_list["id"], "foodId": str(food.id), "quantity": 1}
    api_client.post(api_routes.households_shopping_items, json=existing, headers=unique_user.token)

    plan = recipes_plan(api_client, unique_user, [(recipe, 1)], shoppingListId=shopping_list["id"])
    result = apply_plan(api_client, unique_user, plan["id"])
    assert (result["created"], result["updated"]) == (0, 1)
    assert item_for(list_items(api_client, unique_user, shopping_list["id"]), food)["quantity"] == 3

    # the plan leaves: the quantity that was there before stays
    api_client.put(
        f"{PLANS}/{plan['id']}",
        json={"name": "x", "sourceType": "RECIPES", "recipes": [{"recipeId": str(recipe.id), "scale": 0.5}]},
        headers=unique_user.token,
    )
    apply_plan(api_client, unique_user, plan["id"])
    assert item_for(list_items(api_client, unique_user, shopping_list["id"]), food)["quantity"] == 2


# ----------------------------------------------------------------------------------------------------------------
# Native features stay intact


def test_native_shopping_list_still_works_next_to_a_plan(api_client: TestClient, unique_user: TestUser):
    food, native_food = create_food(unique_user), create_food(unique_user)
    recipe = create_recipe(unique_user, ingredients=[(2, None, food, "")])
    native_recipe = create_recipe(unique_user, ingredients=[(3, None, native_food, "")])
    plan = recipes_plan(api_client, unique_user, [(recipe, 1)])
    list_id = apply_plan(api_client, unique_user, plan["id"])["shoppingListId"]

    # native: add a recipe to the same list
    response = api_client.post(
        api_routes.households_shopping_lists_item_id_recipe(list_id),
        json=[{"recipeId": str(native_recipe.id), "recipeIncrementQuantity": 1}],
        headers=unique_user.token,
    )
    assert response.status_code == 200, response.text
    items = list_items(api_client, unique_user, list_id)
    assert item_for(items, native_food)["quantity"] == 3
    assert item_for(items, food)["quantity"] == 2

    # the plan runs again and leaves the native item alone
    result = apply_plan(api_client, unique_user, plan["id"])
    assert (result["created"], result["updated"], result["deleted"]) == (0, 0, 0)
    assert item_for(list_items(api_client, unique_user, list_id), native_food)["quantity"] == 3

    # native: the list is still listed and can be deleted
    listed = api_client.get(api_routes.households_shopping_lists, headers=unique_user.token).json()["items"]
    assert list_id in [shopping_list["id"] for shopping_list in listed]
    assert (
        api_client.delete(api_routes.households_shopping_lists_item_id(list_id), headers=unique_user.token).status_code
        == 200
    )

    # the plan survives the deletion of its list and builds a new one
    result = apply_plan(api_client, unique_user, plan["id"])
    assert result["shoppingListId"] != list_id
    assert result["created"] == 1


def test_plans_are_scoped_to_the_household(api_client: TestClient, unique_user: TestUser, h2_user: TestUser):
    recipe = create_recipe(unique_user, ingredients=[(1, None, create_food(unique_user), "")])
    plan = recipes_plan(api_client, unique_user, [(recipe, 1)])

    for path in ("", "/preview", "/lines"):
        assert api_client.get(f"{PLANS}/{plan['id']}{path}", headers=h2_user.token).status_code == 404
    assert api_client.post(f"{PLANS}/{plan['id']}/apply", json={}, headers=h2_user.token).status_code == 404
    assert api_client.delete(f"{PLANS}/{plan['id']}", headers=h2_user.token).status_code == 404


def test_plan_validation(api_client: TestClient, unique_user: TestUser):
    def post(payload: dict) -> int:
        return api_client.post(PLANS, json={"name": "x", **payload}, headers=unique_user.token).status_code

    assert post({"sourceType": "EVENT"}) == 422
    assert post({"sourceType": "MEALPLAN", "dateFrom": "2031-01-10", "dateTo": "2031-01-01"}) == 422
    assert post({"sourceType": "RECIPES", "recipes": []}) == 422
    assert post({"sourceType": "RECIPES", "recipes": [{"recipeId": str(uuid4()), "scale": 1}]}) == 404
    assert post({"sourceType": "EVENT", "eventId": str(uuid4())}) == 404
