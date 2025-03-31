from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from psycopg import AsyncConnection
from starlette.responses import Response

from src.repository import root_repository
from src.dependencies import get_broadcast_service
from src.models.models import SessionStatus
from src.service.broadcast import BroadcastService
from src.dependencies import get_db, get_jinja

router = APIRouter(tags=["navbar"])

jinja = get_jinja()


@router.get("/components/root-selector")
@jinja.hx('components/navbar/root_selector.html.j2')
async def root_selector_component(
    db: AsyncConnection = Depends(get_db)):
    """This route serves the root selector component for htmx requests."""

    from src.main import app

    roots = await root_repository.get_all(db)

    return {
        'roots': roots,
        'selected_root': app.state.selected_root
    }

@router.get("/components/root-selector/form")
@jinja.hx('components/navbar/root_selector_form.html.j2')
async def root_selector_form(db: AsyncConnection = Depends(get_db)):
    """This route serves the root selector form component for htmx requests."""
    from src.repository.root import RootRepository

    root_repo = RootRepository()
    recent_roots = await root_repo.get_all(db)

    return {
        'roots': recent_roots
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


@router.get("/root/{root_uri}")
@jinja.hx('components/navbar/root_view.html.j2')
async def view_root(root_uri: str, db: AsyncConnection = Depends(get_db)):
    """This route serves the root view component for htmx requests."""
    from src.repository.root import RootRepository

    root_repo = RootRepository()
    root = await root_repo.get_with_files(db, root_uri)

    if not root:
        return {"error": "Root not found"}

    return {
        'root': root
    }

@router.post("/root/select/{root_uri}")
@jinja.hx('components/navbar/root_selector.html.j2')
async def select_root(root_uri: str,
                      db: AsyncConnection = Depends(get_db),
                      broadcast_service: BroadcastService = Depends(get_broadcast_service)):
    """Select a root as the current working root."""
    from src.main import app

    app.state.selected_root = root_repository.get_by_uri(db, root_uri)

    await broadcast_service.broadcast("root.selected", {"root_uri": root_uri})

    return {
        'roots': root_repository.get_all(db),
        'selected_root': app.state.selected_root
    }
