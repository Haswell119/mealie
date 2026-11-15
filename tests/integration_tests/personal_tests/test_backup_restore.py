from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

from mealie.core.config import get_app_settings
from mealie.services.backups_v2.backup_v2 import BackupV2
from tests.utils.fixture_schemas import TestUser

from .helpers import BASE, create_food, create_person, create_recipe, restriction_ids, verify_food
from .test_shopping_plans import add_stock, apply_plan, recipes_plan


def test_personal_data_survives_a_native_backup_and_restore(api_client: TestClient, unique_user: TestUser):
    ids = restriction_ids(api_client, unique_user)
    food = create_food(unique_user)
    recipe = create_recipe(unique_user, ingredients=[(2, None, food, "")])

    person = create_person(
        api_client, unique_user, "Dominique", consentGiven=True, restrictions=[{"restrictionId": ids["meat"]}]
    )
    verify_food(api_client, unique_user, food.id, ids["gluten"])
    event = api_client.post(
        f"{BASE}/meal-events", json={"name": "Brunch", "startsAt": "2031-05-04T11:30:00"}, headers=unique_user.token
    ).json()
    stock = api_client.post(
        f"{BASE}/pantry",
        json={"foodId": str(food.id), "quantity": 1, "confirmedUsable": True, "expiresOn": "2031-06-01"},
        headers=unique_user.token,
    ).json()
    add_stock(api_client, unique_user, create_food(unique_user), 3)
    plan = recipes_plan(api_client, unique_user, [(recipe, 2)])
    apply_plan(api_client, unique_user, plan["id"])
    inspiration = api_client.post(
        f"{BASE}/inspirations",
        json={"title": "Idée", "kind": "IDEA", "tags": ["été", "rapide"]},
        headers=unique_user.token,
    ).json()
    api_client.post(f"{BASE}/inspirations/{inspiration['id']}/draft", headers=unique_user.token)

    # A restore drops every table. PostgreSQL makes that wait for any open transaction, so end ours first.
    unique_user.repos.session.rollback()

    backup = BackupV2(get_app_settings().DB_URL)
    path = backup.backup()
    backup.restore(path)
    unique_user.repos.session.expire_all()

    # nested values come back as lists and dictionaries, dates as dates
    restored = unique_user.repos
    restored_person = restored.pe_persons.get_one(person["id"])
    assert restored_person.display_name == "Dominique"
    assert isinstance(restored_person.consent_given_at, datetime)
    assert restored_person.restrictions[0].restriction.key == "meat"

    assert restored.pe_meal_events.get_one(event["id"]).starts_at == datetime(2031, 5, 4, 11, 30, tzinfo=UTC)
    assert restored.pe_pantry_items.get_one(stock["id"]).expires_on == date(2031, 6, 1)

    lines = restored.pe_shopping_plan_lines.multi_query({"plan_id": plan["id"]})
    assert len(lines) == 1
    assert lines[0].quantity_to_buy == 3
    assert lines[0].sources[0].recipe_id == recipe.id
    assert lines[0].shopping_list_item_id is not None
    restored_plan = restored.pe_shopping_plans.get_one(plan["id"])
    assert restored_plan.recipes[0].recipe_id == recipe.id
    assert isinstance(restored_plan.computed_at, datetime)

    restored_inspiration = restored.pe_inspirations.get_one(inspiration["id"])
    assert restored_inspiration.tags == ["été", "rapide"]
    assert restored_inspiration.draft.name == "Idée"

    status = restored.pe_food_restriction_status.multi_query({"food_id": food.id})[0]
    assert status.status == "VERIFIED"
    assert isinstance(status.verified_at, datetime)

    # the API still answers after the restore
    assert api_client.get(f"{BASE}/persons/{person['id']}", headers=unique_user.token).status_code == 200
    again = apply_plan(api_client, unique_user, plan["id"])
    assert (again["created"], again["updated"], again["deleted"]) == (0, 0, 0)
