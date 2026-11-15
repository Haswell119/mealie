import json
from types import SimpleNamespace

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from mealie.services.openai import OpenAIService
from mealie.services.openai.openai import OpenAINotEnabledException
from mealie.services.personal.assistant_privacy import Anonymizer
from tests.utils.fixture_schemas import TestUser

from .helpers import BASE, create_food, create_recipe
from .scenario import build_burger_scenario
from .test_shopping_plans import add_stock, item_for, list_items

ASSISTANT = f"{BASE}/assistant"
SECRET_NOTE = "maladie coeliaque diagnostiquée en 2019"


def tool_call(call_id: str, name: str, **arguments) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments, default=str))
    )


def reply(content: str = "", tool_calls: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))])


class FakeProvider:
    """Stands in for the AI provider: plays a script and records every request the application sends."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.script: list = []
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        provider = SimpleNamespace(name="Infomaniak", model="mistral3", timeout=30)
        monkeypatch.setattr(OpenAIService, "_get_provider", lambda *_args, **_kwargs: provider)
        monkeypatch.setattr(OpenAIService, "get_client", lambda *_args, **_kwargs: self)

    async def _create(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs, default=str)))
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    @property
    def sent_text(self) -> str:
        """Everything that left the application, as one string."""
        return json.dumps(self.requests, ensure_ascii=False)

    def tool_result(self, index: int) -> dict:
        """The result of the n-th function call, as the provider received it."""
        results = [m for m in self.requests[-1]["messages"] if m["role"] == "tool"]
        return json.loads(results[index]["content"])


@pytest.fixture()
def provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    return FakeProvider(monkeypatch)


def chat(api_client: TestClient, user: TestUser, message: str, **extra) -> dict:
    response = api_client.post(f"{ASSISTANT}/chat", json={"message": message, **extra}, headers=user.token)
    assert response.status_code == 200, response.text
    return response.json()


# ----------------------------------------------------------------------------------------------------------------
# Availability


def test_assistant_reports_that_no_provider_is_configured(api_client: TestClient, unique_user: TestUser):
    status = api_client.get(f"{ASSISTANT}/status", headers=unique_user.token)
    assert status.status_code == 200
    assert status.json()["enabled"] is False

    body = chat(api_client, unique_user, "Que cuisiner ce soir ?")
    assert body["available"] is False
    assert body["error"] == "NOT_CONFIGURED"


def test_provider_failure_is_an_answer_and_not_an_error(
    api_client: TestClient, unique_user: TestUser, provider: FakeProvider
):
    provider.script = [httpx.ConnectError("provider is down")]
    body = chat(api_client, unique_user, "Bonjour")
    assert body["available"] is False
    assert body["error"] == "PROVIDER_ERROR"

    provider.script = [SimpleNamespace(choices=[])]
    assert chat(api_client, unique_user, "Bonjour")["error"] == "PROVIDER_ERROR"


def test_application_works_while_the_provider_is_down(
    api_client: TestClient, unique_user: TestUser, monkeypatch: pytest.MonkeyPatch
):
    def down(*_args, **_kwargs):
        raise OpenAINotEnabledException()

    monkeypatch.setattr(OpenAIService, "_get_provider", down)
    scenario = build_burger_scenario(api_client, unique_user)

    analysis = api_client.get(f"{BASE}/meal-events/{scenario.event['id']}/analysis", headers=unique_user.token)
    assert analysis.status_code == 200
    plan = api_client.post(
        f"{BASE}/shopping-plans",
        json={"name": "Courses", "sourceType": "EVENT", "eventId": scenario.event["id"]},
        headers=unique_user.token,
    )
    assert plan.status_code == 201
    applied = api_client.post(f"{BASE}/shopping-plans/{plan.json()['id']}/apply", json={}, headers=unique_user.token)
    assert applied.status_code == 200
    assert applied.json()["created"] == 6
    assert chat(api_client, unique_user, "Bonjour")["available"] is False


def test_model_without_function_support_falls_back_to_a_plain_conversation(
    api_client: TestClient, unique_user: TestUser, provider: FakeProvider
):
    request = httpx.Request("POST", "https://api.example.com/chat/completions")
    error = openai.BadRequestError("tools not supported", response=httpx.Response(400, request=request), body=None)
    provider.script = [error, reply("Voici une idée simple.")]

    body = chat(api_client, unique_user, "Une idée ?")
    assert body["available"] is True
    assert body["reply"] == "Voici une idée simple."
    assert "tools" in provider.requests[0]
    assert "tools" not in provider.requests[1]


# ----------------------------------------------------------------------------------------------------------------
# Privacy


def test_anonymizer_replaces_and_restores_names():
    from uuid import uuid4

    sam, anne, anne_marie = uuid4(), uuid4(), uuid4()
    anonymizer = Anonymizer({sam: "Sam", anne: "Anne", anne_marie: "Anne-Marie"})

    scrubbed = anonymizer.scrub("sam et Anne-Marie viennent, Anne aussi. Le samedi.")
    assert "sam " not in scrubbed.lower().replace("samedi", "")
    assert "Anne" not in scrubbed
    assert "samedi" in scrubbed
    assert scrubbed.count("convive") == 3

    assert anonymizer.restore(anonymizer.label(anne_marie)) == "Anne-Marie"
    assert anonymizer.restore(f"Pour {anonymizer.label(sam)}, sans viande.") == "Pour Sam, sans viande."


def test_guest_names_and_notes_never_reach_the_provider(
    api_client: TestClient, unique_user: TestUser, provider: FakeProvider
):
    scenario = build_burger_scenario(api_client, unique_user)
    event_id = scenario.event["id"]

    # give the guests the personal data that must stay inside the application
    for person, name in ((scenario.owner, "Maximilien"), (scenario.vegetarian, "Samantha")):
        update = {
            "displayName": name,
            "isMe": person is scenario.owner,
            "consentGiven": True,
            "notes": SECRET_NOTE,
            "consentNote": "accord donné par message",
            "restrictions": [
                {
                    "restrictionId": r["restrictionId"],
                    "severity": r["severity"],
                    "defaultScope": r["defaultScope"],
                    "appliesWhenCooking": r["appliesWhenCooking"],
                    "notes": SECRET_NOTE,
                }
                for r in person["restrictions"]
            ],
        }
        response = api_client.put(f"{BASE}/persons/{person['id']}", json=update, headers=unique_user.token)
        assert response.status_code == 200, response.text

    provider.script = [
        reply(tool_calls=[tool_call("c1", "get_event_guests", event_id=event_id)]),
        reply(tool_calls=[tool_call("c2", "calculate_portions", event_id=event_id)]),
        reply("Le burger végétarien est prévu pour convive 2 et pour personne d'autre."),
    ]
    body = chat(
        api_client,
        unique_user,
        "Samantha est végétarienne et Maximilien est coeliaque, que proposes-tu ?",
        eventId=event_id,
        history=[{"role": "user", "content": "On reçoit Samantha samedi."}],
    )
    assert body["available"] is True
    assert [call["name"] for call in body["toolCalls"]] == ["get_event_guests", "calculate_portions"]

    sent = provider.sent_text
    for secret in ("Samantha", "Maximilien", SECRET_NOTE, "accord donné par message", "MEDICAL"):
        assert secret not in sent, secret
    for person in [scenario.owner, scenario.vegetarian, *scenario.others]:
        assert person["id"] not in sent
    assert unique_user.email not in sent

    # the provider gets the constraints it needs, without names
    guests = provider.tool_result(0)
    assert guests["guest_count"] == 7
    assert guests["constraints_for_every_portion"] == [
        {"restriction": "gluten", "scope": "ENTIRE_PREPARATION", "severity": "STRICT"}
    ]
    assert len(guests["constraints_for_one_guest"]) == 1
    assert guests["constraints_for_one_guest"][0]["guest"].startswith("convive ")
    assert sorted(guests["constraints_for_one_guest"][0]["constraints"]) == ["fish", "meat"]

    # the name comes back only in what the user reads
    assert "convive 2" in sent or "convive" in sent
    assert "convive" not in body["reply"] or "Samantha" in body["reply"] or "Maximilien" in body["reply"]


# ----------------------------------------------------------------------------------------------------------------
# Controlled functions


def test_read_functions_return_application_data(api_client: TestClient, unique_user: TestUser, provider: FakeProvider):
    scenario = build_burger_scenario(api_client, unique_user)
    rice = create_food(unique_user, "Riz basmati du placard")
    add_stock(api_client, unique_user, rice, 2)
    recipe_id = str(scenario.beef_burger.id)

    provider.script = [
        reply(
            tool_calls=[
                tool_call("c1", "search_recipes", query="Burger", limit=5),
                tool_call("c2", "get_recipe", recipe_id=recipe_id),
                tool_call("c3", "get_available_ingredients"),
                tool_call("c4", "check_dietary_constraints", recipe_id=recipe_id, restrictions=["gluten", "meat"]),
                tool_call("c5", "calculate_portions", event_id=scenario.event["id"]),
                tool_call("c6", "launch_missiles"),
                tool_call("c7", "get_recipe", recipe_id="not-a-uuid"),
            ]
        ),
        reply("Fait."),
    ]
    body = chat(api_client, unique_user, "Regarde mes recettes")
    assert body["reply"] == "Fait."

    search, recipe, stock, check, portions, unknown, invalid = (provider.tool_result(i) for i in range(7))
    assert scenario.beef_burger.name in [r["name"] for r in search["recipes"]]
    assert recipe["servings"] == 4
    assert len(recipe["ingredients"]) == 5
    assert {"food": "Riz basmati du placard", "quantity": 2.0, "unit": ""} in stock["stock"]

    assert check["statuses"] == {"gluten": "UNVERIFIED", "meat": "INCOMPATIBLE"}
    assert "Never state" in check["note"]

    dishes = {dish["label"]: dish for dish in portions["menu"][0]["dishes"]}
    assert (dishes["Boeuf"]["portions"], dishes["Végétarien"]["portions"]) == (6, 1)

    assert "Unknown function" in unknown["error"]
    assert "error" in invalid


def test_shopping_list_proposal_changes_nothing_until_the_user_accepts(
    api_client: TestClient, unique_user: TestUser, provider: FakeProvider
):
    scenario = build_burger_scenario(api_client, unique_user)
    event_id = scenario.event["id"]
    lists_before = api_client.get(f"{BASE}/shopping/lists", headers=unique_user.token).json()["total"]

    provider.script = [
        reply(tool_calls=[tool_call("c1", "draft_shopping_list", event_id=event_id)]),
        reply("J'ai préparé une liste. Acceptez la proposition pour la créer."),
    ]
    body = chat(api_client, unique_user, "Prépare les courses", eventId=event_id)

    # the quantities come from the engine of the application, not from the model
    draft = provider.tool_result(0)
    assert draft["status"] == "PENDING"
    lines = {line["item"]: line for line in draft["lines"]}
    assert lines[scenario.foods["bun"].name]["to_buy"] == 7
    assert lines[scenario.foods["beef"].name]["to_buy"] == 0.9
    assert lines[scenario.foods["bun"].name]["to_check"] == ["gluten:UNVERIFIED"]

    assert len(body["proposals"]) == 1
    proposal = body["proposals"][0]
    assert (proposal["kind"], proposal["status"]) == ("SHOPPING_LIST", "PENDING")

    # nothing was written
    assert api_client.get(f"{BASE}/shopping/lists", headers=unique_user.token).json()["total"] == lists_before
    plans = api_client.get(f"{BASE}/shopping-plans", params={"perPage": -1}, headers=unique_user.token).json()
    assert event_id not in [plan["eventId"] for plan in plans["items"]]

    accepted = api_client.post(f"{ASSISTANT}/proposals/{proposal['id']}/accept", headers=unique_user.token)
    assert accepted.status_code == 200, accepted.text
    result = accepted.json()
    assert result["status"] == "ACCEPTED"
    items = list_items(api_client, unique_user, result["result"]["shopping_list_id"])
    assert item_for(items, scenario.foods["bun"])["quantity"] == 7

    twice = api_client.post(f"{ASSISTANT}/proposals/{proposal['id']}/accept", headers=unique_user.token)
    assert twice.status_code == 400


def test_recipe_variant_proposal_keeps_quantities_and_stays_unverified(
    api_client: TestClient, unique_user: TestUser, provider: FakeProvider
):
    scenario = build_burger_scenario(api_client, unique_user)
    recipe_id = str(scenario.beef_burger.id)
    recipes_before = api_client.get("/api/recipes", headers=unique_user.token).json()["total"]

    provider.script = [
        reply(
            tool_calls=[
                tool_call(
                    "c1",
                    "propose_recipe_variant",
                    recipe_id=recipe_id,
                    title="sans viande",
                    event_id=scenario.event["id"],
                    substitutions=[
                        {"ingredient": "steak haché", "replacement": "Galette de lentilles", "reason": "végétarien"},
                        {"ingredient": "licorne", "replacement": "poudre de fée"},
                    ],
                    notes="Cuisson plus courte.",
                )
            ]
        ),
        reply("Proposition créée."),
    ]
    body = chat(api_client, unique_user, "Une version végétarienne ?")
    proposal = body["proposals"][0]
    assert proposal["kind"] == "RECIPE_VARIANT"

    # the replacement is checked by the rules, and never comes out verified
    checks = provider.tool_result(0)["checks"]
    assert checks and all(check["status"] != "VERIFIED" for check in checks)
    assert api_client.get("/api/recipes", headers=unique_user.token).json()["total"] == recipes_before

    rejected = api_client.post(f"{ASSISTANT}/proposals/{proposal['id']}/reject", headers=unique_user.token)
    assert rejected.json()["status"] == "REJECTED"
    assert api_client.get("/api/recipes", headers=unique_user.token).json()["total"] == recipes_before

    # a second, accepted proposal creates a new recipe and leaves the original alone
    provider.script = [
        reply(
            tool_calls=[
                tool_call(
                    "c1",
                    "propose_recipe_variant",
                    recipe_id=recipe_id,
                    title="sans viande",
                    substitutions=[{"ingredient": "steak haché", "replacement": "Galette de lentilles"}],
                )
            ]
        ),
        reply("Proposition créée."),
    ]
    proposal = chat(api_client, unique_user, "Encore")["proposals"][0]
    accepted = api_client.post(f"{ASSISTANT}/proposals/{proposal['id']}/accept", headers=unique_user.token)
    assert accepted.status_code == 200, accepted.text
    result = accepted.json()["result"]

    variant = api_client.get(f"/api/recipes/{result['recipe_slug']}", headers=unique_user.token).json()
    replaced = [i for i in variant["recipeIngredient"] if i["note"] == "Galette de lentilles"]
    assert len(replaced) == 1
    # quantity and unit come from the original recipe
    assert replaced[0]["quantity"] == 0.6
    assert replaced[0]["unit"]["id"] == str(scenario.units["kilogram"].id)
    assert replaced[0]["food"] is None
    assert len(variant["recipeIngredient"]) == 5

    original = api_client.get(f"/api/recipes/{scenario.beef_burger.slug}", headers=unique_user.token).json()
    assert any(i["food"] and i["food"]["id"] == str(scenario.foods["beef"].id) for i in original["recipeIngredient"])


def test_menu_proposal_adds_dishes_after_acceptance(
    api_client: TestClient, unique_user: TestUser, provider: FakeProvider
):
    scenario = build_burger_scenario(api_client, unique_user)
    dessert = create_recipe(unique_user, "Salade de fruits", ingredients=[(1, None, create_food(unique_user), "")])

    provider.script = [
        reply(
            tool_calls=[
                tool_call(
                    "c1",
                    "propose_menu",
                    event_id=scenario.event["id"],
                    items=[{"course": "DESSERT", "recipe_id": str(dessert.id)}],
                )
            ]
        ),
        reply("Proposition créée."),
    ]
    proposal = chat(api_client, unique_user, "Un dessert ?")["proposals"][0]
    # the dish is checked against every constraint of the event, by the engine of the application
    assert proposal["payload"]["items"][0]["statuses"] == {
        "fish": "UNVERIFIED",
        "gluten": "UNVERIFIED",
        "meat": "UNVERIFIED",
    }

    event = api_client.get(f"{BASE}/meal-events/{scenario.event['id']}", headers=unique_user.token).json()
    assert len(event["menuItems"]) == 1

    api_client.post(f"{ASSISTANT}/proposals/{proposal['id']}/accept", headers=unique_user.token)
    event = api_client.get(f"{BASE}/meal-events/{scenario.event['id']}", headers=unique_user.token).json()
    assert [item["course"] for item in event["menuItems"]] == ["MAIN", "DESSERT"]
    assert len(event["menuItems"][0]["variants"]) == 2


def test_assistant_cannot_reach_another_household(
    api_client: TestClient, unique_user: TestUser, h2_user: TestUser, provider: FakeProvider
):
    scenario = build_burger_scenario(api_client, unique_user)
    provider.script = [
        reply(tool_calls=[tool_call("c1", "get_event_guests", event_id=scenario.event["id"])]),
        reply("Introuvable."),
    ]
    chat(api_client, h2_user, "Montre l'événement")
    assert provider.tool_result(0) == {"error": "Event not found."}


def test_inspiration_structuring_creates_a_proposal(
    api_client: TestClient, unique_user: TestUser, provider: FakeProvider
):
    inspiration = api_client.post(
        f"{BASE}/inspirations",
        json={"title": "Soupe de courge", "kind": "NOTE", "text": "courge, oignon, bouillon, 4 personnes"},
        headers=unique_user.token,
    ).json()
    url = f"{BASE}/inspirations/{inspiration['id']}"

    provider.script = [
        reply(
            'Voici :\n```json\n{"name": "Soupe de courge", "recipe_servings": 4, '
            '"ingredients": ["1 courge", "1 oignon"], "instructions": ["Cuire.", "Mixer."]}\n```'
        )
    ]
    response = api_client.post(f"{url}/structure", headers=unique_user.token)
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert (proposal["kind"], proposal["status"]) == ("RECIPE_DRAFT", "PENDING")

    # still an inspiration until the user accepts the draft, and still not a recipe after that
    assert api_client.get(url, headers=unique_user.token).json()["status"] == "INSPIRATION"
    api_client.post(f"{ASSISTANT}/proposals/{proposal['id']}/accept", headers=unique_user.token)
    after = api_client.get(url, headers=unique_user.token).json()
    assert after["status"] == "DRAFT"
    assert after["draft"]["ingredients"] == ["1 courge", "1 oignon"]
    assert after["recipeId"] is None

    provider.script = [httpx.ConnectError("down")]
    down = api_client.post(f"{url}/structure", headers=unique_user.token)
    assert down.status_code == 400
    assert down.json()["detail"]["exception"] == "ASSISTANT_UNAVAILABLE"
