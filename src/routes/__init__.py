from fastapi import APIRouter
from src.routes.session import router as session_router
from src.routes.registry import router as registry_router
from src.routes.blobs import router as blobs_router
from src.routes.tag import router as tag_router
from src.routes.stash import router as stash_router
from src.routes.navbar import router as navbar_router
api_router = APIRouter()
api_router.include_router(session_router)
api_router.include_router(registry_router)
api_router.include_router(blobs_router)
api_router.include_router(tag_router)
api_router.include_router(stash_router)
api_router.include_router(navbar_router)
