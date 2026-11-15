from fastapi import APIRouter

from . import controller_dietary, controller_meal_events, controller_persons

router = APIRouter()

router.include_router(controller_dietary.router)
router.include_router(controller_persons.router)
router.include_router(controller_meal_events.router)
