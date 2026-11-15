from fastapi import APIRouter

from . import (
    controller_assistant,
    controller_dietary,
    controller_inspirations,
    controller_meal_events,
    controller_pantry,
    controller_persons,
    controller_products,
    controller_shopping_plans,
)

router = APIRouter()

router.include_router(controller_dietary.router)
router.include_router(controller_persons.router)
router.include_router(controller_meal_events.router)
router.include_router(controller_shopping_plans.router)
router.include_router(controller_pantry.router)
router.include_router(controller_pantry.packaging_router)
router.include_router(controller_products.router)
router.include_router(controller_inspirations.router)
router.include_router(controller_assistant.router)
