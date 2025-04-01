from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi import Depends, HTTPException, UploadFile, File, Request
from psycopg import AsyncConnection
from pydantic import BaseModel
from starlette.responses import Response

from src.service.user_state import UserStateService
from src.dependencies import get_user_state_service

from src.repository import root_repository
from src.dependencies import get_broadcast_service
from src.models.models import SessionStatus
from src.service.broadcast import BroadcastService
from src.dependencies import get_db, get_jinja

router = APIRouter(tags=["navbar"])

jinja = get_jinja()



@router.get("/components/root-selector")
@jinja.hx('components/roots/root_selector.html.j2')
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

