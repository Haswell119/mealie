from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from mealie.db.models.personal import PeFoodRestrictionStatus
from mealie.schema.personal.enums import VerificationSource, VerificationStatus
from mealie.services.personal.dietary_service import DietaryService
from mealie.services.personal.errors import PersonalError
from tests.utils.fixture_schemas import TestUser

from .helpers import BASE, create_food, create_person, restriction_ids, verify_food


def test_standard_restrictions_are_created_once(api_client: TestClient, unique_user: TestUser):
    first = restriction_ids(api_client, unique_user)
    second = restriction_ids(api_client, unique_user)

    assert first == second
    assert {"gluten", "meat", "fish", "lactose"} <= set(first)


def test_custom_restriction_crud(api_client: TestClient, unique_user: TestUser):
    payload = {"key": "Cilantro Hate", "name": "Coriandre", "kind": "PREFERENCE"}
    created = api_client.post(f"{BASE}/dietary/restrictions", json=payload, headers=unique_user.token)
    assert created.status_code == 201, created.text
    assert created.json()["key"] == "cilantro_hate"
    assert created.json()["isSystem"] is False

    duplicate = api_client.post(f"{BASE}/dietary/restrictions", json=payload, headers=unique_user.token)
    assert duplicate.status_code == 400

    restriction_id = created.json()["id"]
    deleted = api_client.delete(f"{BASE}/dietary/restrictions/{restriction_id}", headers=unique_user.token)
    assert deleted.status_code == 200


def test_standard_restriction_cannot_be_deleted(api_client: TestClient, unique_user: TestUser):
    gluten = restriction_ids(api_client, unique_user)["gluten"]
    response = api_client.delete(f"{BASE}/dietary/restrictions/{gluten}", headers=unique_user.token)
    assert response.status_code == 400
    assert response.json()["detail"]["exception"] == "RESTRICTION_IS_STANDARD"


def test_unknown_food_is_unverified_and_wheat_is_incompatible(api_client: TestClient, unique_user: TestUser):
    tomato = create_food(unique_user, f"Tomate {uuid4().hex[:6]}")
    wheat = create_food(unique_user, f"Farine de blé {uuid4().hex[:6]}")

    def gluten_state(food_id) -> dict:
        response = api_client.get(f"{BASE}/dietary/foods/{food_id}", headers=unique_user.token)
        assert response.status_code == 200, response.text
        return next(s for s in response.json()["statuses"] if s["restrictionKey"] == "gluten")

    assert gluten_state(tomato.id)["status"] == "UNVERIFIED"
    assert gluten_state(tomato.id)["code"] == "NO_DATA"
    assert gluten_state(tomato.id)["stored"] is False

    assert gluten_state(wheat.id)["status"] == "INCOMPATIBLE"
    assert gluten_state(wheat.id)["code"] == "RULE_MATCH"


def test_person_can_verify_a_food(api_client: TestClient, unique_user: TestUser):
    gluten = restriction_ids(api_client, unique_user)["gluten"]
    food = create_food(unique_user)

    stored = verify_food(api_client, unique_user, food.id, gluten)
    assert stored["status"] == "VERIFIED"
    assert stored["source"] == "MANUAL"
    assert stored["verifiedBy"] == str(unique_user.user_id)

    state = api_client.get(f"{BASE}/dietary/foods/{food.id}", headers=unique_user.token).json()
    gluten_state = next(s for s in state["statuses"] if s["restrictionKey"] == "gluten")
    assert gluten_state["status"] == "VERIFIED"
    assert gluten_state["stored"] is True

    cleared = api_client.delete(f"{BASE}/dietary/foods/{food.id}/restrictions/{gluten}", headers=unique_user.token)
    assert cleared.status_code == 204
    state = api_client.get(f"{BASE}/dietary/foods/{food.id}", headers=unique_user.token).json()
    assert next(s for s in state["statuses"] if s["restrictionKey"] == "gluten")["status"] == "UNVERIFIED"


def test_suggestion_never_marks_a_food_as_verified(api_client: TestClient, unique_user: TestUser):
    gluten = UUID(restriction_ids(api_client, unique_user)["gluten"])
    food = create_food(unique_user)
    service = DietaryService(unique_user.repos)

    for source in (VerificationSource.AI_SUGGESTION, VerificationSource.PRODUCT_LABEL, VerificationSource.RULE):
        stored = service.suggest_food_status(food.id, gluten, VerificationStatus.VERIFIED, source, "label says so")
        assert stored is not None
        assert stored.status == VerificationStatus.UNVERIFIED
        assert stored.source == source

    with pytest.raises(PersonalError):
        service.suggest_food_status(food.id, gluten, VerificationStatus.VERIFIED, VerificationSource.MANUAL)


def test_suggestion_does_not_replace_the_choice_of_a_person(api_client: TestClient, unique_user: TestUser):
    gluten = restriction_ids(api_client, unique_user)["gluten"]
    food = create_food(unique_user)
    verify_food(api_client, unique_user, food.id, gluten)

    service = DietaryService(unique_user.repos)
    result = service.suggest_food_status(
        food.id, UUID(gluten), VerificationStatus.INCOMPATIBLE, VerificationSource.AI_SUGGESTION
    )
    assert result is None
    assert service.food_statuses(food.id)[0].status == VerificationStatus.VERIFIED


def test_database_rejects_a_verified_state_that_is_not_manual(api_client: TestClient, unique_user: TestUser):
    gluten = UUID(restriction_ids(api_client, unique_user)["gluten"])
    food = create_food(unique_user)
    session = unique_user.repos.session

    with pytest.raises(IntegrityError):
        session.execute(
            sa.insert(PeFoodRestrictionStatus).values(
                id=uuid4(),
                group_id=UUID(unique_user.group_id),
                food_id=food.id,
                restriction_id=gluten,
                status="VERIFIED",
                source="AI_SUGGESTION",
            )
        )
        session.commit()
    session.rollback()


def test_person_without_account(api_client: TestClient, unique_user: TestUser):
    person = create_person(api_client, unique_user, "Camille")
    assert person["displayName"] == "Camille"
    assert person["linkedUserId"] is None
    assert person["consentGivenAt"] is None
    assert person["restrictions"] == []


def test_restrictions_need_recorded_consent(api_client: TestClient, unique_user: TestUser):
    ids = restriction_ids(api_client, unique_user)
    payload = {"displayName": "Alex", "restrictions": [{"restrictionId": ids["meat"]}]}

    refused = api_client.post(f"{BASE}/persons", json=payload, headers=unique_user.token)
    assert refused.status_code == 400
    assert refused.json()["detail"]["exception"] == "CONSENT_REQUIRED"

    notes_only = api_client.post(
        f"{BASE}/persons", json={"displayName": "Alex", "notes": "n'aime pas le piment"}, headers=unique_user.token
    )
    assert notes_only.status_code == 400

    accepted = api_client.post(
        f"{BASE}/persons", json={**payload, "consentGiven": True, "consentNote": "oral"}, headers=unique_user.token
    )
    assert accepted.status_code == 201, accepted.text
    body = accepted.json()
    assert body["consentGivenAt"] is not None
    assert body["restrictions"][0]["restriction"]["key"] == "meat"
    assert body["restrictions"][0]["defaultScope"] == "INDIVIDUAL"
    assert body["restrictions"][0]["severity"] == "STRICT"


def test_owner_profile_with_whole_preparation_gluten_restriction(api_client: TestClient, unique_user: TestUser):
    ids = restriction_ids(api_client, unique_user)
    owner = create_person(
        api_client,
        unique_user,
        "Moi",
        isMe=True,
        restrictions=[
            {
                "restrictionId": ids["gluten"],
                "severity": "STRICT",
                "defaultScope": "ENTIRE_PREPARATION",
                "appliesWhenCooking": True,
            }
        ],
    )
    assert owner["linkedUserId"] == str(unique_user.user_id)
    restriction = owner["restrictions"][0]
    assert restriction["defaultScope"] == "ENTIRE_PREPARATION"
    assert restriction["appliesWhenCooking"] is True


def test_person_update_replaces_restrictions_and_preferences(api_client: TestClient, unique_user: TestUser):
    ids = restriction_ids(api_client, unique_user)
    liked, disliked = create_food(unique_user), create_food(unique_user)
    person = create_person(
        api_client,
        unique_user,
        consentGiven=True,
        restrictions=[{"restrictionId": ids["meat"]}, {"restrictionId": ids["fish"]}],
        foodPreferences=[{"foodId": str(liked.id), "kind": "LIKE"}],
    )
    assert len(person["restrictions"]) == 2

    update = {
        "displayName": person["displayName"],
        "appetite": "LARGE",
        "consentGiven": True,
        "restrictions": [{"restrictionId": ids["lactose"], "severity": "MODERATE"}],
        "foodPreferences": [{"foodId": str(disliked.id), "kind": "DISLIKE", "note": "texture"}],
    }
    response = api_client.put(f"{BASE}/persons/{person['id']}", json=update, headers=unique_user.token)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["appetite"] == "LARGE"
    assert [r["restriction"]["key"] for r in body["restrictions"]] == ["lactose"]
    assert [p["food"]["id"] for p in body["foodPreferences"]] == [str(disliked.id)]
    assert body["consentGivenAt"] == person["consentGivenAt"]


def test_deleting_a_person_removes_every_record(api_client: TestClient, unique_user: TestUser):
    ids = restriction_ids(api_client, unique_user)
    person = create_person(api_client, unique_user, consentGiven=True, restrictions=[{"restrictionId": ids["meat"]}])

    deleted = api_client.delete(f"{BASE}/persons/{person['id']}", headers=unique_user.token)
    assert deleted.status_code == 200

    assert api_client.get(f"{BASE}/persons/{person['id']}", headers=unique_user.token).status_code == 404
    assert unique_user.repos.pe_person_restrictions.multi_query({"person_id": person["id"]}) == []


def test_persons_are_not_visible_to_another_household_or_group(
    api_client: TestClient, unique_user: TestUser, h2_user: TestUser, g2_user: TestUser
):
    person = create_person(api_client, unique_user, consentGiven=True, notes="confidentiel")

    for other in (h2_user, g2_user):
        assert api_client.get(f"{BASE}/persons/{person['id']}", headers=other.token).status_code == 404
        listed = api_client.get(f"{BASE}/persons", params={"perPage": -1}, headers=other.token).json()["items"]
        assert person["id"] not in [item["id"] for item in listed]
        update = {"displayName": "x"}
        assert api_client.put(f"{BASE}/persons/{person['id']}", json=update, headers=other.token).status_code == 404
        assert api_client.delete(f"{BASE}/persons/{person['id']}", headers=other.token).status_code == 404


def test_persons_need_authentication(api_client: TestClient):
    assert api_client.get(f"{BASE}/persons").status_code == 401
    assert api_client.get(f"{BASE}/dietary/restrictions").status_code == 401


def test_error_messages_follow_the_language_of_the_request(api_client: TestClient, unique_user: TestUser):
    ids = restriction_ids(api_client, unique_user)
    payload = {"displayName": "Alex", "restrictions": [{"restrictionId": ids["meat"]}]}

    english = api_client.post(f"{BASE}/persons", json=payload, headers=unique_user.token)
    assert english.json()["detail"]["message"].startswith("Record the consent")

    headers = {**unique_user.token, "Accept-Language": "fr-FR"}
    french = api_client.post(f"{BASE}/persons", json=payload, headers=headers)
    assert french.status_code == 400
    assert french.json()["detail"]["exception"] == "CONSENT_REQUIRED"
    assert french.json()["detail"]["message"].startswith("Enregistrez le consentement")

    missing = api_client.get(f"{BASE}/persons/{uuid4()}", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["detail"]["message"] == "Personne introuvable."
