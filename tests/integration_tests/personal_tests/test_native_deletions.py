"""
Deleting native data must keep working when the personal edition refers to it.

PostgreSQL enforces foreign keys and SQLite does not, so the checks on what the database removes
only run on PostgreSQL. The native call must succeed on both.
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from mealie.core.config import get_app_settings
from mealie.repos.all_repositories import get_repositories
from mealie.schema.household.household import HouseholdCreate
from mealie.schema.personal.pantry import PantryItemCreate
from mealie.schema.personal.person import PersonCreate
from mealie.services.household_services.household_service import HouseholdService
from mealie.services.personal.pantry_service import PantryService
from mealie.services.personal.person_service import PersonService
from tests.utils import api_routes
from tests.utils.factories import random_string
from tests.utils.fixture_schemas import TestUser

from .helpers import (
    BASE,
    create_food,
    create_person,
    create_recipe,
    purge_orphans,
    restriction_ids,
    verify_food,
)
from .test_shopping_plans import add_stock, apply_plan, recipes_plan

ENFORCES_FOREIGN_KEYS = get_app_settings().DB_ENGINE == "postgres"


@pytest.fixture(autouse=True)
def remove_what_postgres_would_remove(unique_user: TestUser):
    yield
    if not ENFORCES_FOREIGN_KEYS:
        purge_orphans(unique_user)


def test_native_food_can_be_deleted(api_client: TestClient, unique_user: TestUser):
    ids = restriction_ids(api_client, unique_user)
    food = create_food(unique_user)
    recipe = create_recipe(unique_user, ingredients=[(1, None, food, "")])

    verify_food(api_client, unique_user, food.id, ids["gluten"])
    stock = add_stock(api_client, unique_user, food, 2)
    packaging = api_client.post(
        f"{BASE}/packagings", json={"foodId": str(food.id), "quantity": 500}, headers=unique_user.token
    ).json()
    person = create_person(
        api_client, unique_user, consentGiven=True, foodPreferences=[{"foodId": str(food.id), "kind": "LIKE"}]
    )
    plan = recipes_plan(api_client, unique_user, [(recipe, 5)])
    apply_plan(api_client, unique_user, plan["id"])

    # the recipe and the shopping list still use the food, so remove those native references first
    api_client.delete(api_routes.recipes_slug(recipe.slug), headers=unique_user.token)
    list_id = api_client.get(f"{BASE}/shopping-plans/{plan['id']}", headers=unique_user.token).json()["shoppingListId"]
    api_client.delete(api_routes.households_shopping_lists_item_id(list_id), headers=unique_user.token)

    unique_user.repos.session.rollback()
    response = api_client.delete(api_routes.foods_item_id(food.id), headers=unique_user.token)
    assert response.status_code == 200, response.text

    if ENFORCES_FOREIGN_KEYS:
        unique_user.repos.session.expire_all()
        assert api_client.get(f"{BASE}/pantry/{stock['id']}", headers=unique_user.token).status_code == 404
        assert unique_user.repos.pe_food_packagings.get_one(packaging["id"]) is None
        assert unique_user.repos.pe_food_restriction_status.multi_query({"food_id": food.id}) == []
        refreshed = api_client.get(f"{BASE}/persons/{person['id']}", headers=unique_user.token).json()
        assert refreshed["foodPreferences"] == []
        # the line of the plan stays, without its food
        lines = api_client.get(f"{BASE}/shopping-plans/{plan['id']}/lines", headers=unique_user.token).json()
        assert [line["foodId"] for line in lines] == [None]


def test_native_recipe_in_an_event_menu_can_be_deleted(api_client: TestClient, unique_user: TestUser):
    person = create_person(api_client, unique_user)
    recipe = create_recipe(unique_user, ingredients=[(1, None, create_food(unique_user), "")])
    other = create_recipe(unique_user, ingredients=[(1, None, create_food(unique_user), "")])
    event = api_client.post(f"{BASE}/meal-events", json={"name": "Repas"}, headers=unique_user.token).json()
    api_client.put(
        f"{BASE}/meal-events/{event['id']}/guests", json=[{"personId": person["id"]}], headers=unique_user.token
    )
    menu = [{"course": "MAIN", "variants": [{"recipeId": str(recipe.id)}, {"recipeId": str(other.id)}]}]
    event = api_client.put(f"{BASE}/meal-events/{event['id']}/menu", json=menu, headers=unique_user.token).json()
    item = event["menuItems"][0]
    assignment = {"menuItemId": item["id"], "personId": person["id"], "variantId": item["variants"][0]["id"]}
    api_client.put(f"{BASE}/meal-events/{event['id']}/assignments", json=assignment, headers=unique_user.token)

    unique_user.repos.session.rollback()
    response = api_client.delete(api_routes.recipes_slug(recipe.slug), headers=unique_user.token)
    assert response.status_code == 200, response.text

    analysis = api_client.get(f"{BASE}/meal-events/{event['id']}/analysis", headers=unique_user.token)
    assert analysis.status_code == 200, analysis.text
    if ENFORCES_FOREIGN_KEYS:
        variants = analysis.json()["menu"][0]["variants"]
        assert [variant["recipeId"] for variant in variants] == [str(other.id)]
        assert variants[0]["portions"] == 1
    else:
        # without foreign keys the variant stays and the analysis reports the missing recipe
        assert "RECIPE_NOT_FOUND" in [finding["code"] for finding in analysis.json()["blocking"]]


def test_native_tool_with_a_flag_can_be_deleted(api_client: TestClient, unique_user: TestUser):
    ids = restriction_ids(api_client, unique_user)
    tool = api_client.post(
        api_routes.organizers_tools, json={"name": "Grille-pain partagé"}, headers=unique_user.token
    ).json()
    flagged = api_client.post(
        f"{BASE}/dietary/tools", json={"toolId": tool["id"], "restrictionId": ids["gluten"]}, headers=unique_user.token
    )
    assert flagged.status_code == 201, flagged.text

    unique_user.repos.session.rollback()
    response = api_client.delete(api_routes.organizers_tools_item_id(tool["id"]), headers=unique_user.token)
    assert response.status_code == 200, response.text

    if ENFORCES_FOREIGN_KEYS:
        flags = api_client.get(f"{BASE}/dietary/tools", headers=unique_user.token).json()
        assert tool["id"] not in [flag["toolId"] for flag in flags]


def test_native_food_merge_still_works(api_client: TestClient, unique_user: TestUser):
    kept, merged = create_food(unique_user), create_food(unique_user)
    add_stock(api_client, unique_user, merged, 1)

    unique_user.repos.session.rollback()
    response = api_client.put(
        api_routes.foods_merge, json={"fromFood": str(merged.id), "toFood": str(kept.id)}, headers=unique_user.token
    )
    assert response.status_code == 200, response.text


def test_household_with_personal_data_can_be_deleted(api_client: TestClient, unique_user: TestUser):
    session = unique_user.repos.session
    group_repos = get_repositories(session, group_id=UUID(unique_user.group_id), household_id=None)
    household = HouseholdService.create_household(group_repos, HouseholdCreate(name=random_string()))
    scoped = get_repositories(session, group_id=UUID(unique_user.group_id), household_id=household.id)

    person = PersonService(scoped).create(PersonCreate(display_name="Invité", consent_given=True), unique_user.user_id)
    food = create_food(unique_user)
    stock = PantryService(scoped).create(PantryItemCreate(food_id=food.id, quantity=1))
    event = scoped.pe_meal_events.create(
        {"group_id": UUID(unique_user.group_id), "household_id": household.id, "name": "Repas", "status": "DRAFT"}
    )
    scoped.pe_meal_event_guests.create(
        {
            "group_id": UUID(unique_user.group_id),
            "household_id": household.id,
            "event_id": event.id,
            "person_id": person.id,
        }
    )

    session.rollback()
    group_repos.households.delete(household.id)

    if ENFORCES_FOREIGN_KEYS:
        session.expire_all()
        everything = get_repositories(session, group_id=UUID(unique_user.group_id), household_id=None)
        assert everything.pe_persons.get_one(person.id) is None
        assert everything.pe_pantry_items.get_one(stock.id) is None
        assert everything.pe_meal_events.get_one(event.id) is None
