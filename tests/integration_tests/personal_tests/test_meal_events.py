from fastapi.testclient import TestClient

from tests.utils.fixture_schemas import TestUser

from .helpers import BASE, create_food, create_person, create_recipe, restriction_ids, verify_food
from .scenario import analysis, build_burger_scenario


def variant_by_label(result: dict, label: str) -> dict:
    return next(variant for variant in result["menu"][0]["variants"] if variant["label"] == label)


def test_burger_event_constraints_and_portions(api_client: TestClient, unique_user: TestUser):
    scenario = build_burger_scenario(api_client, unique_user)
    result = analysis(api_client, unique_user, scenario.event["id"])

    assert result["totalPersons"] == 7
    assert result["totalPortions"] == 7

    # the gluten restriction of the cook reaches the whole preparation
    shared = result["constraints"]["shared"]
    assert [(c["restrictionKey"], c["scope"]) for c in shared] == [("gluten", "ENTIRE_PREPARATION")]
    assert shared[0]["personNames"] == ["Moi"]

    # the vegetarian restriction stays on the vegetarian guest
    individual = result["constraints"]["individual"]
    assert len(individual) == 1
    assert individual[0]["personId"] == scenario.vegetarian["id"]
    assert sorted(c["restrictionKey"] for c in individual[0]["constraints"]) == ["fish", "meat"]

    beef = variant_by_label(result, "Boeuf")
    veggie = variant_by_label(result, "Végétarien")

    # six portions may contain meat, one portion is vegetarian
    assert beef["portions"] == 6
    assert veggie["portions"] == 1
    assert veggie["personIds"] == [scenario.vegetarian["id"]]
    assert scenario.vegetarian["id"] not in beef["personIds"]
    assert beef["scale"] == 1.5
    assert veggie["scale"] == 0.25

    # every portion is checked for gluten, the vegetarian portion also for meat and fish
    assert set(beef["statuses"]) == {"gluten"}
    assert set(veggie["statuses"]) == {"fish", "gluten", "meat"}


def test_burger_event_grants_no_automatic_gluten_safety(api_client: TestClient, unique_user: TestUser):
    scenario = build_burger_scenario(api_client, unique_user)
    result = analysis(api_client, unique_user, scenario.event["id"])

    assert result["status"] == "UNVERIFIED"
    assert result["blocking"] == []

    for label in ("Boeuf", "Végétarien"):
        variant = variant_by_label(result, label)
        assert variant["statuses"]["gluten"] == "UNVERIFIED"
        assert all(finding["status"] != "VERIFIED" for finding in variant["findings"])

    # the bun is named "sans gluten": the name is a claim to check, not a proof
    bun_findings = [
        f
        for f in result["toVerify"]
        if f["foodId"] == str(scenario.foods["bun"].id) and f["restrictionKey"] == "gluten"
    ]
    assert bun_findings
    assert all(f["code"] == "FREE_CLAIM" for f in bun_findings)

    # an unknown product is flagged, never cleared
    tomato_findings = [f for f in result["toVerify"] if f["foodId"] == str(scenario.foods["tomato"].id)]
    assert tomato_findings and tomato_findings[0]["code"] == "NO_DATA"

    # the whole preparation gets its cross-contamination checklist
    codes = {(item["code"], item["restrictionKey"]) for item in result["checklist"]}
    assert ("CLEAN_SURFACES", "gluten") in codes
    assert ("DEDICATED_UTENSILS", "gluten") in codes
    assert ("CHECK_LABELS", "gluten") in codes


def test_event_becomes_verified_only_after_manual_verification(api_client: TestClient, unique_user: TestUser):
    scenario = build_burger_scenario(api_client, unique_user)
    gluten = scenario.restrictions["gluten"]

    for food in scenario.foods.values():
        verify_food(api_client, unique_user, food.id, gluten)

    result = analysis(api_client, unique_user, scenario.event["id"])
    assert variant_by_label(result, "Boeuf")["status"] == "VERIFIED"
    # the vegetarian portion still has unverified foods for meat and fish
    assert variant_by_label(result, "Végétarien")["statuses"]["gluten"] == "VERIFIED"
    assert variant_by_label(result, "Végétarien")["status"] == "UNVERIFIED"

    for key in ("meat", "fish"):
        for name in ("bun", "veggie_patty", "tomato", "salad", "cheddar"):
            verify_food(api_client, unique_user, scenario.foods[name].id, scenario.restrictions[key])

    result = analysis(api_client, unique_user, scenario.event["id"])
    assert result["status"] == "VERIFIED"
    assert result["toVerify"] == []


def test_gluten_in_any_variant_blocks_the_event(api_client: TestClient, unique_user: TestUser):
    scenario = build_burger_scenario(api_client, unique_user)
    wheat_bun = create_food(unique_user, "Pain burger au blé")
    wheat_burger = create_recipe(unique_user, servings=4, ingredients=[(4, None, wheat_bun, "")])

    menu = [
        {
            "id": scenario.menu_item_id,
            "course": "MAIN",
            "title": "Burgers",
            "variants": [
                {"recipeId": str(wheat_burger.id), "label": "Boeuf"},
                {
                    "id": scenario.variants["Végétarien"],
                    "recipeId": str(scenario.veggie_burger.id),
                    "label": "Végétarien",
                },
            ],
        }
    ]
    response = api_client.put(f"{BASE}/meal-events/{scenario.event['id']}/menu", json=menu, headers=unique_user.token)
    assert response.status_code == 200, response.text

    result = analysis(api_client, unique_user, scenario.event["id"])
    assert result["status"] == "INCOMPATIBLE"
    assert result["canPlan"] is False
    blocking = [f for f in result["blocking"] if f["restrictionKey"] == "gluten"]
    assert blocking and blocking[0]["code"] == "RULE_MATCH"
    assert blocking[0]["recipeName"] == wheat_burger.name

    refused = api_client.put(
        f"{BASE}/meal-events/{scenario.event['id']}/status",
        json={"status": "PLANNED", "acknowledgeUnverified": True},
        headers=unique_user.token,
    )
    assert refused.status_code == 400
    assert refused.json()["detail"]["exception"] == "EVENT_HAS_BLOCKING_ISSUES"


def test_planning_needs_an_acknowledgement_of_unverified_items(api_client: TestClient, unique_user: TestUser):
    scenario = build_burger_scenario(api_client, unique_user)
    url = f"{BASE}/meal-events/{scenario.event['id']}/status"

    refused = api_client.put(url, json={"status": "PLANNED"}, headers=unique_user.token)
    assert refused.status_code == 400
    assert refused.json()["detail"]["exception"] == "UNVERIFIED_NOT_ACKNOWLEDGED"

    accepted = api_client.put(url, json={"status": "PLANNED", "acknowledgeUnverified": True}, headers=unique_user.token)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "PLANNED"
    assert "PLANNED" in [entry["action"] for entry in accepted.json()["history"]]


def test_changing_the_guests_reopens_a_planned_event(api_client: TestClient, unique_user: TestUser):
    scenario = build_burger_scenario(api_client, unique_user)
    event_id = scenario.event["id"]
    api_client.put(
        f"{BASE}/meal-events/{event_id}/status",
        json={"status": "PLANNED", "acknowledgeUnverified": True},
        headers=unique_user.token,
    )

    guests = [{"personId": person["id"]} for person in [scenario.owner, scenario.vegetarian]]
    response = api_client.put(f"{BASE}/meal-events/{event_id}/guests", json=guests, headers=unique_user.token)
    assert response.json()["status"] == "DRAFT"

    result = analysis(api_client, unique_user, event_id)
    assert result["totalPersons"] == 2
    assert variant_by_label(result, "Boeuf")["portions"] == 1
    assert variant_by_label(result, "Végétarien")["portions"] == 1


def test_absent_guest_and_appetite_change_the_portions(api_client: TestClient, unique_user: TestUser):
    scenario = build_burger_scenario(api_client, unique_user)
    guests = [
        {"personId": scenario.owner["id"], "appetiteOverride": "LARGE"},
        {"personId": scenario.vegetarian["id"], "appetiteOverride": "SMALL"},
        {"personId": scenario.others[0]["id"], "attending": False},
        {"personId": scenario.others[1]["id"]},
    ]
    api_client.put(f"{BASE}/meal-events/{scenario.event['id']}/guests", json=guests, headers=unique_user.token)

    result = analysis(api_client, unique_user, scenario.event["id"])
    assert result["totalPersons"] == 3
    assert variant_by_label(result, "Boeuf")["portions"] == 2.25
    assert variant_by_label(result, "Végétarien")["portions"] == 0.75


def test_leftovers_add_portions(api_client: TestClient, unique_user: TestUser):
    scenario = build_burger_scenario(api_client, unique_user)
    update = {"name": scenario.event["name"], "cookPersonId": scenario.owner["id"], "leftoverPortions": 2}
    response = api_client.put(f"{BASE}/meal-events/{scenario.event['id']}", json=update, headers=unique_user.token)
    assert response.status_code == 200, response.text

    result = analysis(api_client, unique_user, scenario.event["id"])
    assert result["totalPortions"] == 9
    assert variant_by_label(result, "Boeuf")["portions"] == 8


def test_vegetarian_without_a_compatible_variant_blocks_the_event(api_client: TestClient, unique_user: TestUser):
    scenario = build_burger_scenario(api_client, unique_user)
    menu = [
        {
            "course": "MAIN",
            "title": "Burgers",
            "variants": [{"recipeId": str(scenario.beef_burger.id), "label": "Boeuf"}],
        }
    ]
    api_client.put(f"{BASE}/meal-events/{scenario.event['id']}/menu", json=menu, headers=unique_user.token)

    result = analysis(api_client, unique_user, scenario.event["id"])
    assert result["menu"][0]["unassignedPersonIds"] == [scenario.vegetarian["id"]]
    assert result["canPlan"] is False
    codes = {(f["code"], f["restrictionKey"]) for f in result["blocking"]}
    assert ("NO_VARIANT", "meat") in codes


def test_manual_assignment_that_breaks_a_restriction_is_reported(api_client: TestClient, unique_user: TestUser):
    scenario = build_burger_scenario(api_client, unique_user)
    payload = {
        "menuItemId": scenario.menu_item_id,
        "personId": scenario.vegetarian["id"],
        "variantId": scenario.variants["Boeuf"],
    }
    response = api_client.put(
        f"{BASE}/meal-events/{scenario.event['id']}/assignments", json=payload, headers=unique_user.token
    )
    assert response.status_code == 200, response.text

    result = analysis(api_client, unique_user, scenario.event["id"])
    assert variant_by_label(result, "Boeuf")["portions"] == 7
    assert ("MANUAL_ASSIGNMENT", "meat") in {(f["code"], f["restrictionKey"]) for f in result["blocking"]}

    payload["variantId"] = None
    api_client.put(f"{BASE}/meal-events/{scenario.event['id']}/assignments", json=payload, headers=unique_user.token)
    result = analysis(api_client, unique_user, scenario.event["id"])
    assert variant_by_label(result, "Végétarien")["portions"] == 1


def test_whole_meal_restriction_applies_to_every_portion(api_client: TestClient, unique_user: TestUser):
    ids = restriction_ids(api_client, unique_user)
    guest = create_person(
        api_client,
        unique_user,
        consentGiven=True,
        restrictions=[{"restrictionId": ids["pork"], "defaultScope": "ENTIRE_MEAL"}],
    )
    other = create_person(api_client, unique_user)
    bacon = create_food(unique_user, "Lardons de porc fumés")
    recipe = create_recipe(unique_user, servings=2, ingredients=[(100, None, bacon, "")])

    event = api_client.post(f"{BASE}/meal-events", json={"name": "Dîner"}, headers=unique_user.token).json()
    api_client.put(
        f"{BASE}/meal-events/{event['id']}/guests",
        json=[{"personId": guest["id"]}, {"personId": other["id"]}],
        headers=unique_user.token,
    )
    api_client.put(
        f"{BASE}/meal-events/{event['id']}/menu",
        json=[{"course": "MAIN", "variants": [{"recipeId": str(recipe.id)}]}],
        headers=unique_user.token,
    )

    result = analysis(api_client, unique_user, event["id"])
    assert [(c["restrictionKey"], c["scope"]) for c in result["constraints"]["shared"]] == [("pork", "ENTIRE_MEAL")]
    assert result["status"] == "INCOMPATIBLE"
    # a whole-meal restriction asks for a label check, not for a preparation checklist
    assert {item["code"] for item in result["checklist"]} == {"CHECK_LABELS"}


def test_scope_override_needs_a_reason_and_is_recorded(api_client: TestClient, unique_user: TestUser):
    scenario = build_burger_scenario(api_client, unique_user)
    event_id = scenario.event["id"]
    payload = {
        "personId": scenario.owner["id"],
        "restrictionId": scenario.restrictions["gluten"],
        "scope": "INDIVIDUAL",
    }

    without_reason = api_client.post(
        f"{BASE}/meal-events/{event_id}/overrides", json=payload, headers=unique_user.token
    )
    assert without_reason.status_code == 422

    payload["reason"] = "Le traiteur fournit ma portion séparément"
    response = api_client.post(f"{BASE}/meal-events/{event_id}/overrides", json=payload, headers=unique_user.token)
    assert response.status_code == 201, response.text
    event = response.json()
    assert event["overrides"][0]["createdBy"] == str(unique_user.user_id)
    assert "RESTRICTION_SCOPE_OVERRIDDEN" in [entry["action"] for entry in event["history"]]

    result = analysis(api_client, unique_user, event_id)
    assert result["constraints"]["shared"] == []
    owner_constraints = next(p for p in result["constraints"]["individual"] if p["personId"] == scenario.owner["id"])
    assert owner_constraints["constraints"][0]["origins"] == ["EVENT_OVERRIDE"]

    removed = api_client.delete(
        f"{BASE}/meal-events/{event_id}/overrides/{event['overrides'][0]['id']}", headers=unique_user.token
    )
    assert removed.status_code == 200
    result = analysis(api_client, unique_user, event_id)
    assert result["constraints"]["shared"][0]["scope"] == "ENTIRE_PREPARATION"


def test_recipe_without_servings_is_reported(api_client: TestClient, unique_user: TestUser):
    person = create_person(api_client, unique_user)
    recipe = create_recipe(unique_user, servings=0, ingredients=[(1, None, create_food(unique_user), "")])
    event = api_client.post(f"{BASE}/meal-events", json={"name": "Test"}, headers=unique_user.token).json()
    api_client.put(
        f"{BASE}/meal-events/{event['id']}/guests", json=[{"personId": person["id"]}], headers=unique_user.token
    )
    api_client.put(
        f"{BASE}/meal-events/{event['id']}/menu",
        json=[{"course": "DESSERT", "variants": [{"recipeId": str(recipe.id)}]}],
        headers=unique_user.token,
    )

    result = analysis(api_client, unique_user, event["id"])
    variant = result["menu"][0]["variants"][0]
    assert variant["error"] == "MISSING_SERVINGS"
    assert variant["scale"] is None
    assert result["canPlan"] is False


def test_event_crud_and_scoping(api_client: TestClient, unique_user: TestUser, h2_user: TestUser):
    scenario = build_burger_scenario(api_client, unique_user)
    event_id = scenario.event["id"]

    listed = api_client.get(f"{BASE}/meal-events", params={"perPage": -1}, headers=unique_user.token).json()["items"]
    assert event_id in [event["id"] for event in listed]

    assert api_client.get(f"{BASE}/meal-events/{event_id}", headers=h2_user.token).status_code == 404
    assert api_client.get(f"{BASE}/meal-events/{event_id}/analysis", headers=h2_user.token).status_code == 404
    assert api_client.delete(f"{BASE}/meal-events/{event_id}", headers=h2_user.token).status_code == 404

    deleted = api_client.delete(f"{BASE}/meal-events/{event_id}", headers=unique_user.token)
    assert deleted.status_code == 200
    assert api_client.get(f"{BASE}/meal-events/{event_id}", headers=unique_user.token).status_code == 404

    # deleting a person who was a guest of a deleted event works
    assert (
        api_client.delete(f"{BASE}/persons/{scenario.vegetarian['id']}", headers=unique_user.token).status_code == 200
    )
