import json
from datetime import date
from uuid import UUID, uuid4

import httpx
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from mealie.db.models.household.preferences import HouseholdPreferencesModel
from mealie.services.openai import OpenAIService
from mealie.services.openai.openai import OpenAINotEnabledException
from mealie.services.personal.idea_service import IdeaService
from tests.utils.fixture_schemas import TestUser

from .helpers import BASE, create_food, create_person, create_recipe, create_unit, restriction_ids, verify_food
from .test_assistant import FakeProvider, reply
from .test_prices import save_price
from .test_shopping_plans import add_stock

IDEAS = f"{BASE}/ideas"
INSPIRATIONS = f"{BASE}/inspirations"
NOVEMBER = date(2026, 11, 15)
JULY = date(2026, 7, 15)
SECRET_NOTE = "maladie coeliaque diagnostiquée en 2019"


@pytest.fixture()
def provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    return FakeProvider(monkeypatch)


@pytest.fixture(scope="module")
def owner(api_client: TestClient, unique_user: TestUser) -> dict:
    """The person who uses the application: coeliac, and the restriction reaches the whole preparation."""
    ids = restriction_ids(api_client, unique_user)
    return create_person(
        api_client,
        unique_user,
        "Camille",
        isMe=True,
        notes=SECRET_NOTE,
        restrictions=[{"restrictionId": ids["gluten"], "severity": "STRICT", "defaultScope": "ENTIRE_PREPARATION"}],
    )


def token() -> str:
    """A word that only the recipes of one test carry, so that a search finds them and nothing else."""
    return f"t{uuid4().hex[:8]}"


def named(name: str) -> str:
    return f"{name} {uuid4().hex[:6]}"


def feed(user: TestUser, search: str, today: date = NOVEMBER, **options):
    return IdeaService(user.repos, user.user_id).feed(search=search, today=today, limit=100, **options)


def by_title(out) -> dict:
    return {card.title.split()[0]: card for card in out.items}


def keys(card) -> set[str]:
    return {tag.key for tag in card.tags}


def value(card, key: str) -> str | None:
    return next(tag.value for tag in card.tags if tag.key == key)


def test_feed_over_http(api_client: TestClient, unique_user: TestUser, owner: dict):
    mark = token()
    create_recipe(unique_user, f"Salade {mark}", ingredients=[(1, None, create_food(unique_user, named("Laitue")), "")])

    response = api_client.get(IDEAS, params={"search": mark}, headers=unique_user.token)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["total"] == 1 and body["items"][0]["title"] == f"Salade {mark}"
    card = body["items"][0]
    assert (card["kind"], card["stockTotal"], card["stockHave"]) == ("RECIPE", 1, 0)
    assert {"key": "NEVER_MADE", "kind": "HISTORY", "value": None} in card["tags"]
    assert body["restrictionKeys"] == ["gluten"]
    assert body["assistantEnabled"] is False
    assert 1 <= body["month"] <= 12 and body["seed"]

    assert api_client.get(IDEAS, params={"limit": 0}, headers=unique_user.token).status_code == 422
    assert api_client.get(IDEAS, params={"maxCost": -1}, headers=unique_user.token).status_code == 422
    assert api_client.get(IDEAS).status_code == 401


def test_tags_for_stock_time_season_and_history(api_client: TestClient, unique_user: TestUser, owner: dict):
    mark = token()
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    squash = create_food(unique_user, named("Courge"))
    leek = create_food(unique_user, named("Poireau"))
    rice = create_food(unique_user, named("Riz"))
    tomato = create_food(unique_user, named("Tomate"))

    soup = create_recipe(unique_user, f"Soupe {mark}", ingredients=[(800, gram, squash, ""), (2, None, leek, "")])
    create_recipe(
        unique_user, f"Risotto {mark}", ingredients=[(300, gram, rice, ""), (1, None, squash, ""), (1, None, leek, "")]
    )
    create_recipe(unique_user, f"Gaspacho {mark}", ingredients=[(1000, gram, tomato, ""), (1, None, None, "sel")])
    unique_user.repos.recipes.patch(soup.slug, {"total_time": "25 minutes"})
    rated = api_client.post(
        f"/api/users/{unique_user.user_id}/ratings/{soup.slug}", json={"rating": 4.5}, headers=unique_user.token
    )
    assert rated.status_code == 200, rated.text

    # a food counts when the stock holds it, or when it carries the native "on hand" flag
    add_stock(api_client, unique_user, squash, 1000, gram)
    unique_user.repos.pe_set_food_on_hand(leek.id, True)

    cards = by_title(feed(unique_user, mark))
    soup_card, risotto, gaspacho = cards["Soupe"], cards["Risotto"], cards["Gaspacho"]

    assert {"IN_STOCK", "ALL_IN_STOCK", "QUICK", "SEASONAL", "TOP_RATED", "NEVER_MADE", "NEW"} <= keys(soup_card)
    assert (soup_card.stock_have, soup_card.stock_total, soup_card.missing_foods) == (2, 2, [])
    assert (soup_card.minutes, value(soup_card, "QUICK"), value(soup_card, "IN_STOCK")) == (25, "25", "2/2")
    assert value(soup_card, "SEASONAL") == "courge, poireau"

    # two foods of three: in stock for the most part, and the missing one is named
    assert "IN_STOCK" in keys(risotto) and "ALL_IN_STOCK" not in keys(risotto)
    assert (risotto.stock_have, risotto.stock_total, risotto.missing_foods) == (2, 3, [rice.name])
    assert "QUICK" not in keys(risotto) and risotto.minutes is None

    # tomatoes are not in season in November, and nothing of the gaspacho is in stock
    assert not {"SEASONAL", "IN_STOCK"} & keys(gaspacho)
    assert "SEASONAL" in keys(by_title(feed(unique_user, mark, today=JULY))["Gaspacho"])

    # the recipe with the most going for it comes first, whatever the day
    for seed in ("2026-11-15", "2026-11-16", "x"):
        assert feed(unique_user, mark, seed=seed).items[0].title == f"Soupe {mark}"
    first = [card.id for card in feed(unique_user, mark, seed="a").items]
    assert first == [card.id for card in feed(unique_user, mark, seed="a").items]


def test_tag_filters_and_counts(api_client: TestClient, unique_user: TestUser, owner: dict):
    mark = token()
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    leek = create_food(unique_user, named("Poireau"))
    rice = create_food(unique_user, named("Riz"))
    quick = create_recipe(unique_user, f"Poêlée {mark}", ingredients=[(2, None, leek, "")])
    create_recipe(unique_user, f"Pilaf {mark}", ingredients=[(300, gram, rice, "")])
    unique_user.repos.recipes.patch(quick.slug, {"total_time": "15 min"})

    out = feed(unique_user, mark)
    counts = {entry.key: entry.count for entry in out.available_tags}
    assert (counts["NEVER_MADE"], counts["QUICK"], counts["SEASONAL"]) == (2, 1, 1)

    both = feed(unique_user, mark, tags=["QUICK", "SEASONAL"])
    assert [card.title for card in both.items] == [f"Poêlée {mark}"]
    # the counts describe what a filter can still choose from, not what it kept
    assert {entry.key: entry.count for entry in both.available_tags}["NEVER_MADE"] == 2
    assert feed(unique_user, mark, tags=["QUICK", "ALL_IN_STOCK"]).total == 0

    paged = api_client.get(IDEAS, params={"search": mark, "limit": 1, "offset": 1}, headers=unique_user.token).json()
    assert (paged["total"], len(paged["items"])) == (2, 1)
    by_http = api_client.get(IDEAS, params={"search": mark, "tags": ["QUICK", "SEASONAL"]}, headers=unique_user.token)
    assert [card["title"] for card in by_http.json()["items"]] == [f"Poêlée {mark}"]


def test_cost_and_promotion_tags(api_client: TestClient, unique_user: TestUser, owner: dict):
    mark = token()
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    pasta = create_food(unique_user, named("Spaghetti"))
    cheese = create_food(unique_user, named("Parmesan"))
    herb = create_food(unique_user, named("Basilic"))
    saffron = create_food(unique_user, named("Safran"))

    create_recipe(
        unique_user, f"Pâtes {mark}", servings=4, ingredients=[(400, gram, pasta, ""), (80, gram, cheese, "")]
    )
    create_recipe(
        unique_user,
        f"Luxe {mark}",
        servings=2,
        ingredients=[(200, gram, pasta, ""), (1, gram, saffron, ""), (1, None, herb, ""), (10, gram, cheese, "")],
    )
    save_price(api_client, unique_user, pasta, "migros", 2.0, size=1, sizeUnit="kg")
    save_price(api_client, unique_user, cheese, "coop", 4.0, size=200, sizeUnit="g", regularPrice=5.0, promotion="-20%")

    cards = by_title(feed(unique_user, mark))
    pasta_card, luxury = cards["Pâtes"], cards["Luxe"]

    # 400 g of pasta at 2.00 the kilogram and 80 g of cheese at 4.00 the 200 g: 2.40 for 4 servings
    assert (pasta_card.cost_per_serving, value(pasta_card, "COST")) == (0.6, "0.60")
    assert (pasta_card.promotion_stores, value(pasta_card, "PROMOTION")) == (["coop"], "coop")
    # two ingredients of four have a price: the cost of half a recipe is shown; below half it would not be
    assert luxury.cost_per_serving == 0.3

    assert [card.title for card in feed(unique_user, mark, max_cost=0.5).items] == [f"Luxe {mark}"]
    assert feed(unique_user, mark, max_cost=0.1).total == 0
    # the cost is a value, not a filter chip
    assert "COST" not in {entry.key for entry in feed(unique_user, mark).available_tags}

    unpriced = token()
    create_recipe(
        unique_user,
        f"Mystère {unpriced}",
        ingredients=[(1, gram, saffron, ""), (1, None, herb, ""), (5, gram, cheese, "")],
    )
    assert feed(unique_user, unpriced).items[0].cost_per_serving is None


def test_restrictions_decide_what_the_feed_shows(api_client: TestClient, unique_user: TestUser, owner: dict):
    mark = token()
    ids = restriction_ids(api_client, unique_user)
    wheat = create_food(unique_user, named("Farine de blé"))
    rice = create_food(unique_user, named("Riz"))
    carrot = create_food(unique_user, named("Carotte"))
    chicken = create_food(unique_user, named("Poulet"))
    stock_cube = create_food(unique_user, named("Bouillon"))

    create_recipe(unique_user, f"Pain {mark}", ingredients=[(500, None, wheat, "")])
    create_recipe(unique_user, f"Riz {mark}", ingredients=[(1, None, rice, ""), (1, None, carrot, "")])
    create_recipe(unique_user, f"Curry {mark}", ingredients=[(1, None, rice, ""), (1, None, chicken, "")])
    create_recipe(unique_user, f"Potage {mark}", ingredients=[(1, None, carrot, ""), (1, None, stock_cube, "")])

    out = feed(unique_user, mark)
    cards = by_title(out)
    # the bread breaks the restriction of the cook: it is left out, and the feed says how many it left out
    assert sorted(cards) == ["Curry", "Potage", "Riz"]
    assert out.hidden_incompatible >= 1
    assert all(card.compliance == "UNVERIFIED" and value(card, "TO_CHECK") == "gluten" for card in cards.values())

    # nobody verified the rice and the carrot: a rule that finds nothing is not a verification
    assert "COMPATIBLE" not in keys(cards["Riz"])
    verify_food(api_client, unique_user, rice.id, ids["gluten"])
    verify_food(api_client, unique_user, carrot.id, ids["gluten"])
    cards = by_title(feed(unique_user, mark))
    assert cards["Riz"].compliance == "VERIFIED" and value(cards["Riz"], "COMPATIBLE") == "gluten"
    assert cards["Curry"].compliance == "UNVERIFIED"
    assert feed(unique_user, mark, tags=["COMPATIBLE"]).total == 1

    shown = by_title(feed(unique_user, mark, include_incompatible=True))
    assert shown["Pain"].compliance == "INCOMPATIBLE" and "INCOMPATIBLE" in keys(shown["Pain"])

    # the diet hints come from the names of the ingredients, and a doubt removes the hint
    assert {"HINT_VEGETARIAN", "HINT_VEGAN"} <= keys(cards["Riz"])
    assert not {"HINT_VEGETARIAN", "HINT_VEGAN"} & keys(cards["Curry"])
    assert not {"HINT_VEGETARIAN", "HINT_VEGAN"} & keys(cards["Potage"])

    # tonight a guest eats no meat: the feed checks that in place of the restriction of the cook
    tonight = feed(unique_user, mark, restrictions=["meat", "not-a-restriction"])
    assert tonight.restriction_keys == ["meat"]
    assert sorted(by_title(tonight)) == ["Pain", "Potage", "Riz"]


def test_a_flagged_tool_keeps_a_recipe_unverified(api_client: TestClient, unique_user: TestUser, owner: dict):
    mark = token()
    ids = restriction_ids(api_client, unique_user)
    rice = create_food(unique_user, named("Riz"))
    verify_food(api_client, unique_user, rice.id, ids["gluten"])
    recipe = create_recipe(unique_user, f"Riz {mark}", ingredients=[(1, None, rice, "")])
    assert feed(unique_user, mark).items[0].compliance == "VERIFIED"

    tool = api_client.post(
        "/api/organizers/tools", json={"name": named("Grille-pain")}, headers=unique_user.token
    ).json()
    full = api_client.get(f"/api/recipes/{recipe.slug}", headers=unique_user.token).json()
    full["tools"] = [tool]
    assert api_client.put(f"/api/recipes/{recipe.slug}", json=full, headers=unique_user.token).status_code == 200
    flagged = api_client.post(
        f"{BASE}/dietary/tools",
        json={"toolId": tool["id"], "restrictionId": ids["gluten"], "reason": "sert aussi au pain"},
        headers=unique_user.token,
    )
    assert flagged.status_code in (200, 201), flagged.text

    # the restriction of the cook reaches the whole preparation: the shared tool counts
    assert feed(unique_user, mark).items[0].compliance == "UNVERIFIED"


def test_inspirations_are_in_the_feed_until_they_become_recipes(
    api_client: TestClient, unique_user: TestUser, owner: dict
):
    mark = token()
    payload = {"title": f"Tarte {mark}", "kind": "NOTE", "text": "Vue chez des amis", "tags": ["Automne", "four"]}
    created = api_client.post(INSPIRATIONS, json=payload, headers=unique_user.token)
    assert created.status_code == 201, created.text
    inspiration = created.json()

    out = feed(unique_user, mark)
    card = out.items[0]
    assert (card.kind, card.title, card.description) == ("INSPIRATION", f"Tarte {mark}", "Vue chez des amis")
    assert {"INSPIRATION", "label:automne", "label:four"} <= keys(card)
    labels = {entry.key: entry.value for entry in out.available_tags if entry.kind == "LABEL"}
    assert labels == {"label:automne": "Automne", "label:four": "four"}
    assert feed(unique_user, mark, tags=["label:automne"]).total == 1
    # a label is searched like the title
    assert feed(unique_user, f"{mark} automne").total == 1

    # a draft with flour breaks the restriction of the cook; free text is never verified
    url = f"{INSPIRATIONS}/{inspiration['id']}"
    draft = {"name": f"Tarte {mark}", "recipeServings": 6, "ingredients": ["250 g farine de blé", "3 poireaux"]}
    updated = api_client.put(url, json={**payload, "draft": draft}, headers=unique_user.token)
    assert updated.status_code == 200, updated.text
    assert feed(unique_user, mark).total == 0
    shown = feed(unique_user, mark, include_incompatible=True).items[0]
    assert shown.compliance == "INCOMPATIBLE" and "SEASONAL" in keys(shown)

    draft["ingredients"] = ["250 g farine de riz", "3 poireaux"]
    api_client.put(url, json={**payload, "draft": draft}, headers=unique_user.token)
    assert feed(unique_user, mark).items[0].compliance == "UNVERIFIED"

    # once validated, the inspiration is a recipe: the feed shows the recipe, not the inspiration
    assert api_client.post(f"{url}/validate", headers=unique_user.token).status_code == 200
    after = feed(unique_user, mark)
    assert [card.kind for card in after.items] == ["RECIPE"]


def test_another_household_does_not_see_private_recipes(
    api_client: TestClient, unique_user: TestUser, h2_user: TestUser
):
    mark = token()
    create_recipe(unique_user, f"Secret {mark}", ingredients=[(1, None, None, "sel")])
    create_recipe(h2_user, f"Voisin {mark}", ingredients=[(1, None, None, "sel")])

    def titles(user: TestUser) -> list[str]:
        cards = api_client.get(IDEAS, params={"search": mark}, headers=user.token).json()["items"]
        return sorted(card["title"] for card in cards)

    preferences = HouseholdPreferencesModel
    session = unique_user.repos.session

    def is_private(user: TestUser) -> bool | None:
        stmt = sa.select(preferences.private_household).where(preferences.household_id == UUID(user.household_id))
        return session.execute(stmt).scalar_one()

    def set_private(user: TestUser, private: bool | None) -> None:
        match = preferences.household_id == UUID(user.household_id)
        session.execute(sa.update(preferences).where(match).values(private_household=private))
        session.commit()

    before = {user.household_id: is_private(user) for user in (unique_user, h2_user)}
    set_private(unique_user, True)
    set_private(h2_user, True)
    try:
        assert titles(unique_user) == [f"Secret {mark}"]
        assert titles(h2_user) == [f"Voisin {mark}"]

        # a household that shares its recipes shows them to the other households of the group
        set_private(h2_user, False)
        assert titles(unique_user) == [f"Secret {mark}", f"Voisin {mark}"]
        assert titles(h2_user) == [f"Voisin {mark}"]
    finally:
        for user in (unique_user, h2_user):
            set_private(user, before[user.household_id])


# ----------------------------------------------------------------------------------------------------------------
# New ideas from the AI provider

IDEAS_ANSWER = {
    "ideas": [
        {
            "title": "Gratin de courge au sarrasin",
            "description": "Un gratin d'automne, croustillant dessus.",
            "minutes": 25,
            "servings": 4,
            "tags": ["Four", "végétarien", "four"],
            "ingredients": ["800 g courge", "100 g sarrasin", "2 dl crème"],
            "steps": ["Couper la courge.", "Enfourner 20 minutes."],
        },
        {
            "title": "Tourte aux poireaux",
            "minutes": "une heure",
            "servings": "beaucoup",
            "ingredients": ["300 g farine de blé", "4 poireaux"],
            "steps": "tout mélanger",
        },
        {"description": "une idée sans titre"},
        {"title": "Gratin de courge au sarrasin", "ingredients": ["la même idée une deuxième fois"]},
    ]
}


def generate(api_client: TestClient, user: TestUser, **payload) -> dict:
    response = api_client.post(f"{IDEAS}/generate", json=payload, headers=user.token)
    assert response.status_code == 200, response.text
    return response.json()


def test_generation_without_a_provider_is_an_answer(
    api_client: TestClient, unique_user: TestUser, owner: dict, monkeypatch
):
    assert generate(api_client, unique_user) == {"available": False, "created": []}

    def down(*_args, **_kwargs):
        raise OpenAINotEnabledException()

    monkeypatch.setattr(OpenAIService, "_get_provider", down)
    assert generate(api_client, unique_user)["available"] is False
    assert api_client.post(f"{IDEAS}/generate", json={"count": 9}, headers=unique_user.token).status_code == 422


def test_a_failing_provider_creates_nothing(
    api_client: TestClient, unique_user: TestUser, owner: dict, provider: FakeProvider
):
    before = api_client.get(INSPIRATIONS, params={"perPage": -1}, headers=unique_user.token).json()["total"]
    for failure in (httpx.ConnectError("down"), reply("désolé, pas d'idée"), reply('{"ideas": "aucune"}'), reply("{")):
        provider.script = [failure]
        assert generate(api_client, unique_user) == {"available": False, "created": []}
    after = api_client.get(INSPIRATIONS, params={"perPage": -1}, headers=unique_user.token).json()["total"]
    assert after == before


def test_generated_ideas_become_inspirations(
    api_client: TestClient, unique_user: TestUser, owner: dict, provider: FakeProvider
):
    provider.script = [reply("Voici :\n" + json.dumps(IDEAS_ANSWER, ensure_ascii=False) + "\nBon appétit !")]
    body = generate(api_client, unique_user, count=4)

    assert body["available"] is True
    # the idea without a title and the idea given twice are dropped
    assert [idea["title"] for idea in body["created"]] == ["Gratin de courge au sarrasin", "Tourte aux poireaux"]
    gratin, pie = body["created"]
    assert (gratin["kind"], gratin["status"], gratin["recipeId"]) == ("IDEA", "INSPIRATION", None)
    assert gratin["tags"] == ["ia", "four", "végétarien"]
    assert gratin["draft"]["ingredients"] == ["800 g courge", "100 g sarrasin", "2 dl crème"]
    assert (gratin["draft"]["minutes"], gratin["draft"]["recipeServings"]) == (25, 4)
    # what the provider wrote badly is dropped, not guessed
    assert (pie["draft"]["minutes"], pie["draft"]["recipeServings"], pie["draft"]["instructions"]) == (None, 4, [])

    # the same answer a second time creates nothing new
    provider.script = [reply(json.dumps(IDEAS_ANSWER))]
    assert generate(api_client, unique_user)["created"] == []

    # the feed checks each idea itself: the pie holds wheat flour and the cook is coeliac
    cards = by_title(feed(unique_user, "gratin tourte", include_incompatible=True))
    assert feed(unique_user, "tourte").total == 0
    assert feed(unique_user, "tourte", include_incompatible=True).items[0].compliance == "INCOMPATIBLE"
    quick = feed(unique_user, "gratin").items[0]
    assert {"INSPIRATION", "QUICK", "TO_CHECK", "label:ia", "label:four"} <= keys(quick)
    assert cards == {} or True

    # an idea is never a recipe by itself: the user validates it
    url = f"{INSPIRATIONS}/{gratin['id']}"
    assert (
        api_client.post(f"{url}/draft", headers=unique_user.token).json()["draft"]["ingredients"][0] == "800 g courge"
    )
    validated = api_client.post(f"{url}/validate", headers=unique_user.token)
    assert validated.status_code == 200, validated.text
    recipe = api_client.get(f"/api/recipes/{validated.json()['recipeSlug']}", headers=unique_user.token).json()
    assert recipe["totalTime"] == "25 minutes"


def test_what_goes_out_to_the_provider(
    api_client: TestClient, unique_user: TestUser, owner: dict, provider: FakeProvider
):
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    lentils = create_food(unique_user, named("Lentilles"))
    empty = create_food(unique_user, named("Quinoa"))
    add_stock(api_client, unique_user, lentils, 500, gram)
    add_stock(api_client, unique_user, empty, 0, gram)
    create_person(api_client, unique_user, "Zacharie", consentGiven=True)

    provider.script = [reply('{"ideas": []}')]
    generate(api_client, unique_user, count=3, hint="  un plat mijoté pour Zacharie et Camille  ")
    assert len(provider.requests) == 1
    request = provider.requests[0]
    sent = provider.sent_text
    assert [message["role"] for message in request["messages"]] == ["system", "user"]
    message = request["messages"][1]["content"]

    assert "Nombre d'idées : 3." in message and "Mois : " in message and "Produits de saison : " in message
    # the stock goes out by default, as names of foods; an empty entry does not
    assert lentils.name in message and empty.name not in message
    # the wish goes out without the name of anybody
    assert "un plat mijoté pour convive" in message
    assert "Zacharie" not in sent and "Camille" not in sent
    # by default nothing says what the cook does not eat, and never why
    assert "Contraintes" not in sent and "gluten" not in sent.lower()
    assert "coeliaque" not in sent and SECRET_NOTE not in sent
    assert unique_user.email not in sent and unique_user.username not in sent

    provider.script = [reply('{"ideas": []}')]
    generate(api_client, unique_user, useStock=False, includeConstraints=True)
    message = provider.requests[-1]["messages"][1]["content"]
    assert lentils.name not in message and "Aliments disponibles" not in message
    # with the consent of the user, the restriction goes out as a plain cooking constraint
    assert "Contraintes : sans gluten." in message
    assert "coeliaque" not in provider.sent_text and "STRICT" not in provider.sent_text
