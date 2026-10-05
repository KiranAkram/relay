from fastapi import APIRouter

from app.api.routes import (
    dashboard,
    flags,
    handovers,
    items,
    login,
    patients,
    private,
    tasks,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(handovers.router)
api_router.include_router(dashboard.router)
api_router.include_router(tasks.router)
api_router.include_router(flags.router)
api_router.include_router(patients.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)
