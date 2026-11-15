from fastapi import APIRouter, Depends

from . import (
    controller_assistant,
    controller_dietary,
    controller_ideas,
    controller_inspirations,
    controller_meal_events,
    controller_pantry,
    controller_persons,
    controller_prices,
    controller_products,
    controller_shopping_plans,
)
from ._base import remember_locale

router = APIRouter(dependencies=[Depends(remember_locale)])

router.include_router(controller_dietary.router)
router.include_router(controller_persons.router)
router.include_router(controller_meal_events.router)
router.include_router(controller_shopping_plans.router)
router.include_router(controller_pantry.router)
router.include_router(controller_pantry.packaging_router)
router.include_router(controller_products.router)
router.include_router(controller_prices.router)
router.include_router(controller_prices.budget_router)
router.include_router(controller_inspirations.router)
router.include_router(controller_ideas.router)
router.include_router(controller_assistant.router)
