from fastapi import APIRouter
from src.components.dialog.routes import router as session_router
from src.components.registry.routes import router as registry_router
from src.components.blob.routes import router as blobs_router
from src.components.tag.routes import router as tag_router
from src.components.stash.routes import router as stash_router
from src.components.navigation.routes import router as navbar_router
from src.components.root.routes import router as root_router


api_router = APIRouter()
api_router.include_router(session_router)
api_router.include_router(registry_router)
api_router.include_router(blobs_router)
api_router.include_router(tag_router)
api_router.include_router(stash_router)
api_router.include_router(navbar_router)
api_router.include_router(root_router)
