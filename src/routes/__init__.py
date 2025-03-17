from fastapi import APIRouter
from src.routes.session import router as session_router
from src.routes.registry import router as registry_router
api_router = APIRouter()
api_router.include_router(session_router)
api_router.include_router(registry_router)
