from fastapi import APIRouter

from app.api.routes import experiments, items, users, utils

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(experiments.router)
