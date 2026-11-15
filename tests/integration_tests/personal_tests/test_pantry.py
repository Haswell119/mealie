from fastapi.testclient import TestClient

from tests.utils import api_routes
from tests.utils.fixture_schemas import TestUser

from .helpers import BASE, create_food, create_recipe, create_unit
from .test_shopping_plans import add_stock, apply_plan, item_for, list_items, recipes_plan, update_item

PANTRY = f"{BASE}/pantry"


def stock_of(api_client: TestClient, user: TestUser, food) -> list[dict]:
    params = {"perPage": -1, "queryFilter": f'foodId = "{food.id}"'}
    response = api_client.get(PANTRY, params=params, headers=user.token)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def on_hand(user: TestUser, food) -> bool:
    household = user.repos.households.get_one(user.household_id)
    refreshed = user.repos.ingredient_foods.get_one(food.id)
    return household.slug in refreshed.households_with_ingredient_food


def test_stock_crud(api_client: TestClient, unique_user: TestUser):
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    food = create_food(unique_user)

    item = add_stock(api_client, unique_user, food, 500, gram, confirmed=False)
    assert item["food"]["name"] == food.name
    assert item["unit"]["standardUnit"] == "gram"
    assert item["confirmedUsable"] is False
    assert item["confirmedAt"] is None

    update = {
        "foodId": str(food.id),
        "unitId": str(gram.id),
        "quantity": 450,
        "confirmedUsable": True,
        "expiresOn": "2031-01-31",
        "location": "Placard",
    }
    response = api_client.put(f"{PANTRY}/{item['id']}", json=update, headers=unique_user.token)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["quantity"] == 450
    assert body["confirmedAt"] is not None
    assert body["expiresOn"] == "2031-01-31"

    assert api_client.delete(f"{PANTRY}/{item['id']}", headers=unique_user.token).status_code == 200
    assert stock_of(api_client, unique_user, food) == []


def test_adjusting_the_stock_never_goes_below_zero(api_client: TestClient, unique_user: TestUser):
    food = create_food(unique_user)
    item = add_stock(api_client, unique_user, food, 3)

    response = api_client.post(f"{PANTRY}/{item['id']}/adjust", json={"delta": -1.5}, headers=unique_user.token)
    assert response.json()["quantity"] == 1.5
    response = api_client.post(f"{PANTRY}/{item['id']}/adjust", json={"delta": -10}, headers=unique_user.token)
    assert response.json()["quantity"] == 0


def test_stock_keeps_the_native_on_hand_flag_current(api_client: TestClient, unique_user: TestUser):
    food = create_food(unique_user)
    assert on_hand(unique_user, food) is False

    item = add_stock(api_client, unique_user, food, 2)
    assert on_hand(unique_user, food) is True

    api_client.post(f"{PANTRY}/{item['id']}/adjust", json={"delta": -2}, headers=unique_user.token)
    assert on_hand(unique_user, food) is False

    api_client.post(f"{PANTRY}/{item['id']}/adjust", json={"delta": 1}, headers=unique_user.token)
    assert on_hand(unique_user, food) is True

    api_client.delete(f"{PANTRY}/{item['id']}", headers=unique_user.token)
    assert on_hand(unique_user, food) is False


def test_expired_stock_is_not_counted(api_client: TestClient, unique_user: TestUser):
    food = create_food(unique_user)
    recipe = create_recipe(unique_user, ingredients=[(2, None, food, "")])
    payload = {"foodId": str(food.id), "quantity": 5, "confirmedUsable": True, "expiresOn": "2020-01-01"}
    assert api_client.post(PANTRY, json=payload, headers=unique_user.token).status_code == 201

    plan = recipes_plan(api_client, unique_user, [(recipe, 1)])
    preview = api_client.get(f"{BASE}/shopping-plans/{plan['id']}/preview", headers=unique_user.token).json()
    assert preview["lines"][0]["quantityFromStock"] == 0
    assert preview["lines"][0]["quantityToBuy"] == 2


def test_bought_items_go_into_the_stock_once(api_client: TestClient, unique_user: TestUser):
    bought, open_food = create_food(unique_user), create_food(unique_user)
    recipe = create_recipe(unique_user, ingredients=[(4, None, bought, ""), (1, None, open_food, "")])
    plan = recipes_plan(api_client, unique_user, [(recipe, 1)])
    list_id = apply_plan(api_client, unique_user, plan["id"])["shoppingListId"]
    update_item(api_client, unique_user, item_for(list_items(api_client, unique_user, list_id), bought), checked=True)

    response = api_client.post(f"{PANTRY}/receive", json={"shoppingListId": list_id}, headers=unique_user.token)
    assert response.status_code == 200, response.text
    assert response.json()["received"] == 1
    assert [(entry["quantity"], entry["confirmedUsable"]) for entry in stock_of(api_client, unique_user, bought)] == [
        (4, True)
    ]
    assert stock_of(api_client, unique_user, open_food) == []

    again = api_client.post(f"{PANTRY}/receive", json={"shoppingListId": list_id}, headers=unique_user.token).json()
    assert (again["received"], again["skipped"]) == (0, 1)
    assert stock_of(api_client, unique_user, bought)[0]["quantity"] == 4

    # the bought item is still on the native list, still checked
    assert item_for(list_items(api_client, unique_user, list_id), bought)["checked"] is True


def test_cooking_a_plan_takes_what_it_needed_out_of_the_stock(api_client: TestClient, unique_user: TestUser):
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    kilogram = create_unit(unique_user, standard_quantity=1, standard_unit="kilogram")
    flour, eggs = create_food(unique_user), create_food(unique_user)
    recipe = create_recipe(unique_user, ingredients=[(300, gram, flour, ""), (2, None, eggs, "")])
    add_stock(api_client, unique_user, flour, 1, kilogram)
    add_stock(api_client, unique_user, eggs, 2)

    plan = recipes_plan(api_client, unique_user, [(recipe, 1)])
    apply_plan(api_client, unique_user, plan["id"])

    response = api_client.post(f"{BASE}/shopping-plans/{plan['id']}/consume", headers=unique_user.token)
    assert response.status_code == 200, response.text
    assert response.json()["plan"]["status"] == "DONE"
    assert response.json()["consumed"] == 2

    assert stock_of(api_client, unique_user, flour)[0]["quantity"] == 0.7
    assert stock_of(api_client, unique_user, eggs) == []

    twice = api_client.post(f"{BASE}/shopping-plans/{plan['id']}/consume", headers=unique_user.token)
    assert twice.status_code == 400


def test_default_packaging_is_unique_per_food(api_client: TestClient, unique_user: TestUser):
    food = create_food(unique_user)
    url = f"{BASE}/packagings"
    first = api_client.post(url, json={"foodId": str(food.id), "quantity": 500}, headers=unique_user.token).json()
    second = api_client.post(url, json={"foodId": str(food.id), "quantity": 1000}, headers=unique_user.token).json()
    assert second["isDefault"] is True

    listed = api_client.get(url, params={"perPage": -1}, headers=unique_user.token).json()["items"]
    defaults = {item["id"]: item["isDefault"] for item in listed if item["foodId"] == str(food.id)}
    assert defaults == {first["id"]: False, second["id"]: True}

    assert (
        api_client.post(url, json={"foodId": str(food.id), "quantity": 0}, headers=unique_user.token).status_code == 422
    )
    assert api_client.delete(f"{url}/{first['id']}", headers=unique_user.token).status_code == 200


def test_stock_is_scoped_to_the_household(api_client: TestClient, unique_user: TestUser, h2_user: TestUser):
    food = create_food(unique_user)
    item = add_stock(api_client, unique_user, food, 2)

    assert api_client.get(f"{PANTRY}/{item['id']}", headers=h2_user.token).status_code == 404
    assert stock_of(api_client, h2_user, food) == []
    assert api_client.delete(f"{PANTRY}/{item['id']}", headers=h2_user.token).status_code == 404
    listed = api_client.get(api_routes.households_shopping_lists, headers=h2_user.token)
    assert listed.status_code == 200
