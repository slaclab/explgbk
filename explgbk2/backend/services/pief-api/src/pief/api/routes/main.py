from fastapi import APIRouter

from pief.api.routes import entries, instruments, logbooks, tags, users, utils

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(instruments.router)
api_router.include_router(entries.router)
api_router.include_router(logbooks.router)
api_router.include_router(tags.router)
