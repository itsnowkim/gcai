from fastapi import APIRouter

from app.api.routes.context_package import router as context_package_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(context_package_router, tags=["analyze"])
api_router.include_router(health_router, tags=["health"])
