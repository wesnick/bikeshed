from fastapi import APIRouter
from src.routes.flow import router as flow_router
from src.routes.session import router as session_router

api_router = APIRouter()
api_router.include_router(flow_router)
api_router.include_router(session_router)
