"""The reference scenario: seven persons, a coeliac cook, one vegetarian guest, burgers."""

from dataclasses import dataclass, field
from uuid import uuid4

from fastapi.testclient import TestClient

from mealie.schema.recipe.recipe import RecipeOut
from mealie.schema.recipe.recipe_ingredient import IngredientFoodOut, IngredientUnitOut
from tests.utils.fixture_schemas import TestUser

from .helpers import BASE, create_food, create_person, create_recipe, create_unit, restriction_ids


@dataclass
class BurgerScenario:
    event: dict
    owner: dict
    vegetarian: dict
    others: list[dict]
    beef_burger: RecipeOut
    veggie_burger: RecipeOut
    foods: dict[str, IngredientFoodOut]
    units: dict[str, IngredientUnitOut]
    restrictions: dict[str, str]
    menu_item_id: str = ""
    variants: dict[str, str] = field(default_factory=dict)


def build_burger_scenario(api_client: TestClient, user: TestUser) -> BurgerScenario:
    ids = restriction_ids(api_client, user)
    suffix = uuid4().hex[:6]

    owner = create_person(
        api_client,
        user,
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
    vegetarian = create_person(
        api_client,
        user,
        "Sam",
        consentGiven=True,
        restrictions=[
            {"restrictionId": ids["meat"], "defaultScope": "INDIVIDUAL"},
            {"restrictionId": ids["fish"], "defaultScope": "INDIVIDUAL"},
        ],
    )
    others = [create_person(api_client, user, f"Invité {index}") for index in range(1, 6)]

    gram = create_unit(user, f"gramme {suffix}", 1, "gram")
    kilogram = create_unit(user, f"kilogramme {suffix}", 1, "kilogram")
    foods = {
        "bun": create_food(user, f"Pain burger sans gluten {suffix}"),
        "beef": create_food(user, f"Steak haché de boeuf {suffix}"),
        "veggie_patty": create_food(user, f"Galette de haricots rouges {suffix}"),
        "tomato": create_food(user, f"Tomate {suffix}"),
        "salad": create_food(user, f"Salade {suffix}"),
        "cheddar": create_food(user, f"Cheddar {suffix}"),
    }

    common = [
        (4, None, foods["bun"], ""),
        (200, gram, foods["tomato"], ""),
        (100, gram, foods["salad"], ""),
        (4, None, foods["cheddar"], "tranches"),
    ]
    beef_burger = create_recipe(
        user, f"Burger boeuf {suffix}", servings=4, ingredients=[*common, (0.6, kilogram, foods["beef"], "")]
    )
    veggie_burger = create_recipe(
        user, f"Burger végétarien {suffix}", servings=4, ingredients=[*common, (4, None, foods["veggie_patty"], "")]
    )

    response = api_client.post(
        f"{BASE}/meal-events",
        json={"name": f"Soirée burgers {suffix}", "cookPersonId": owner["id"], "startsAt": "2026-12-05T19:00:00"},
        headers=user.token,
    )
    assert response.status_code == 201, response.text
    event = response.json()

    guests = [{"personId": person["id"]} for person in [owner, vegetarian, *others]]
    response = api_client.put(f"{BASE}/meal-events/{event['id']}/guests", json=guests, headers=user.token)
    assert response.status_code == 200, response.text

    menu = [
        {
            "course": "MAIN",
            "title": "Burgers",
            "variants": [
                {"recipeId": str(beef_burger.id), "label": "Boeuf"},
                {"recipeId": str(veggie_burger.id), "label": "Végétarien"},
            ],
        }
    ]
    response = api_client.put(f"{BASE}/meal-events/{event['id']}/menu", json=menu, headers=user.token)
    assert response.status_code == 200, response.text
    event = response.json()

    item = event["menuItems"][0]
    return BurgerScenario(
        event=event,
        owner=owner,
        vegetarian=vegetarian,
        others=others,
        beef_burger=beef_burger,
        veggie_burger=veggie_burger,
        foods=foods,
        units={"gram": gram, "kilogram": kilogram},
        restrictions=ids,
        menu_item_id=item["id"],
        variants={variant["label"]: variant["id"] for variant in item["variants"]},
    )


def analysis(api_client: TestClient, user: TestUser, event_id: str) -> dict:
    response = api_client.get(f"{BASE}/meal-events/{event_id}/analysis", headers=user.token)
    assert response.status_code == 200, response.text
    return response.json()
