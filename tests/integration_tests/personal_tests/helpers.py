"""Builders for the integration tests of the personal edition."""

from uuid import UUID

import sqlalchemy as sa
from fastapi.testclient import TestClient

from mealie.db.models._model_base import SqlAlchemyBase
from mealie.schema.recipe.recipe import RecipeDraft, RecipeOut
from mealie.schema.recipe.recipe_ingredient import (
    IngredientFoodOut,
    IngredientFoodSave,
    IngredientUnitOut,
    IngredientUnitSave,
    RecipeIngredient,
)
from tests.utils.factories import random_string
from tests.utils.fixture_schemas import TestUser

BASE = "/api/households"


def restriction_ids(api_client: TestClient, user: TestUser) -> dict[str, str]:
    response = api_client.get(f"{BASE}/dietary/restrictions", headers=user.token)
    assert response.status_code == 200, response.text
    return {restriction["key"]: restriction["id"] for restriction in response.json()}


def create_person(api_client: TestClient, user: TestUser, name: str | None = None, **fields) -> dict:
    payload = {"displayName": name or random_string(), **fields}
    response = api_client.post(f"{BASE}/persons", json=payload, headers=user.token)
    assert response.status_code == 201, response.text
    return response.json()


def create_food(user: TestUser, name: str | None = None) -> IngredientFoodOut:
    return user.repos.ingredient_foods.create(
        IngredientFoodSave(name=name or random_string(), group_id=UUID(user.group_id))
    )


def create_unit(
    user: TestUser, name: str | None = None, standard_quantity: float | None = None, standard_unit: str | None = None
) -> IngredientUnitOut:
    return user.repos.ingredient_units.create(
        IngredientUnitSave(
            name=name or random_string(),
            group_id=UUID(user.group_id),
            standard_quantity=standard_quantity,
            standard_unit=standard_unit,
        )
    )


def create_recipe(
    user: TestUser,
    name: str | None = None,
    servings: float = 4,
    ingredients: list[tuple[float | None, IngredientUnitOut | None, IngredientFoodOut | None, str]] | None = None,
) -> RecipeOut:
    """Create a recipe. Each ingredient is (quantity, unit, food, note)."""
    recipe = user.repos.recipes.create(
        RecipeDraft(
            user_id=user.user_id,
            group_id=UUID(user.group_id),
            name=name or random_string(),
            recipe_servings=servings,
            recipe_ingredient=[
                RecipeIngredient(quantity=quantity, unit=unit, food=food, note=note)
                for quantity, unit, food, note in ingredients or []
            ],
        )
    )
    return recipe


def verify_food(api_client: TestClient, user: TestUser, food_id, restriction_id: str, status: str = "VERIFIED"):
    response = api_client.put(
        f"{BASE}/dietary/foods/{food_id}/restrictions/{restriction_id}",
        json={"status": status},
        headers=user.token,
    )
    assert response.status_code == 200, response.text
    return response.json()


def purge_orphans(user: TestUser) -> None:
    """
    Delete the rows of the personal edition whose native parent is gone.

    PostgreSQL does this through the delete rules of the foreign keys. SQLite does not enforce foreign
    keys, so a test that deletes native data on SQLite removes what PostgreSQL would have removed.
    """
    session = user.repos.session
    tables = [table for name, table in SqlAlchemyBase.metadata.tables.items() if name.startswith("pe_")]

    removed = True
    while removed:
        removed = False
        for table in tables:
            for foreign_key in table.foreign_keys:
                column = foreign_key.parent
                target = foreign_key.column
                orphaned = sa.and_(column.is_not(None), column.not_in(sa.select(target)))
                if column.nullable and foreign_key.ondelete == "SET NULL":
                    result = session.execute(sa.update(table).where(orphaned).values({column.name: None}))
                else:
                    result = session.execute(sa.delete(table).where(orphaned))
                removed = removed or result.rowcount > 0
    session.commit()
