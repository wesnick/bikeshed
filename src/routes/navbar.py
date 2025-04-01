from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi import Depends, HTTPException, UploadFile, File, Request
from psycopg import AsyncConnection
from pydantic import BaseModel
from starlette.responses import Response

# Add these imports
from src.service.user_state import UserStateService
from src.dependencies import get_user_state_service
# Ensure Depends is imported if not already
from fastapi import Depends

from src.repository import root_repository
from src.dependencies import get_broadcast_service
from src.models.models import SessionStatus
from src.service.broadcast import BroadcastService
from src.dependencies import get_db, get_jinja

router = APIRouter(tags=["navbar"])

jinja = get_jinja()

## Request Models
class RootSelectRequest(BaseModel):
    root_uri: str


@router.get("/components/root-selector")
@jinja.hx('components/navbar/root_selector.html.j2')
async def root_selector_component(
    db: AsyncConnection = Depends(get_db),
    user_state_service: UserStateService = Depends(get_user_state_service) # Add this dependency
):
    """This route serves the root selector component for htmx requests."""

    from src.repository.root import RootRepository

    root_repo = RootRepository()
    roots = await root_repo.get_all(db)
    selected_roots = user_state_service.get('selected_roots', default=[])

    return {
        'roots': roots,
        'selected_roots': selected_roots
    }

@router.get("/components/navbar-notifications")
@jinja.hx('components/navbar/navbar-notifications.html.j2')
async def navbar_component(db: AsyncConnection = Depends(get_db)):
    """This route serves the navbar component for htmx requests."""
    from src.repository.session import SessionRepository

    session_repo = SessionRepository()
    active_sessions = await session_repo.get_active_sessions(db)

    running_sessions = [s for s in active_sessions if s.status == SessionStatus.RUNNING]
    waiting_sessions = [s for s in active_sessions if s.status == SessionStatus.WAITING_FOR_INPUT]

    return {
        'total_running': len(running_sessions),
        'total_waiting': len(waiting_sessions),
        'running_sessions': running_sessions,
        'waiting_sessions': waiting_sessions
    }


@router.post("/root/select")
@jinja.hx('components/navbar/root_selector.html.j2')
async def select_root(root_select: RootSelectRequest,
                      db: AsyncConnection = Depends(get_db),
                      user_state_service: UserStateService = Depends(get_user_state_service)
                     ):
    """Select a root as the current working root."""
    from src.repository.root import RootRepository

    root_repo = RootRepository()
    selected_root_obj = await root_repo.get_by_uri(db, root_select.root_uri)

    # Get the current list of selected roots
    current_selected_roots = user_state_service.get('selected_roots', default=[])

    if selected_root_obj:
        if selected_root_obj.uri not in current_selected_roots:
            current_selected_roots.append(selected_root_obj.uri)
            user_state_service.set('selected_roots', current_selected_roots)

    # Fetch all roots again for the response
    roots = await root_repo.get_all(db)

    return {
        'roots': roots,
        'roots': roots,
        'selected_roots': current_selected_roots
    }


@router.post("/root/deselect")
@jinja.hx('components/navbar/root_selector.html.j2')
async def deselect_root(root_deselect: RootSelectRequest,
                        db: AsyncConnection = Depends(get_db),
                        user_state_service: UserStateService = Depends(get_user_state_service)
                       ):
    """Deselect a root from the current working set."""
    from src.repository.root import RootRepository

    # Get the current list of selected roots
    current_selected_roots = user_state_service.get('selected_roots', default=[])

    # Remove the root if it exists in the list
    if root_deselect.root_uri in current_selected_roots:
        current_selected_roots.remove(root_deselect.root_uri)
        user_state_service.set('selected_roots', current_selected_roots)

    # Fetch all roots again for the response
    root_repo = RootRepository()
    roots = await root_repo.get_all(db)

    return {
        'roots': roots,
        'selected_roots': current_selected_roots
    }


@router.get("/root")
@jinja.hx('components/navbar/root_view.html.j2')
async def view_root(root_uri: str, db: AsyncConnection = Depends(get_db)):
    """This route serves the root view component for htmx requests."""
    from src.repository.root import RootRepository

    from src.service.logging import logger
    logger.warning(f"Root URI: {root_uri}")

    root_repo = RootRepository()
    root = await root_repo.get_with_files(db, root_uri)

    if not root:
        return {"error": "Root not found"}

    return {
        'root': root
    }

