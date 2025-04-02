from fastapi import APIRouter, Request, Depends
from psycopg import AsyncConnection

from src.service.user_state import UserStateService
from src.dependencies import get_user_state_service

from src.core.models import SessionStatus
from src.core.registry import Registry
from src.dependencies import get_db, get_jinja, get_registry
from src.components.repositories import session_repository

import uuid



router = APIRouter(tags=["navbar"])

jinja = get_jinja("src/components/navigation/templates")



@router.get("/components/left-sidebar")
@jinja.hx('left_sidebar.html.j2')
async def left_sidebar_component(db: AsyncConnection = Depends(get_db), registry: Registry = Depends(get_registry)) -> dict:
    """This route serves the left sidebar component for htmx requests."""
    sessions = await session_repository.get_recent_sessions(db)

    session_templates = registry.session_templates

    return {
        "flows": [],
        "sessions": sessions,
        "tools": [],
        "prompts": [],
        "session_templates": session_templates,
    }


class PathBasedTemplateSelector:

    @staticmethod
    def parse_request_parts(request: Request):
        from urllib.parse import urlparse
        return urlparse(request.headers.get('hx-current-url')).path.strip('/').split('/')

    def get_component(self, request: Request, error: Exception | None) -> str:
        from urllib.parse import urlparse
        url_parts = urlparse(request.headers.get('hx-current-url')).path.strip('/').split('/')

        from src.service.logging import logger
        logger.warning(f"Url parts: {url_parts}")

        if len(url_parts) < 2:
            return 'empty.html.j2'

        # switch statement
        match url_parts[0]:
            case 'session':
                # test if uuid
                try:
                    uuid.UUID(url_parts[1])
                    return 'session_context.html.j2'
                except ValueError:
                    pass

        return 'empty.html.j2'

@router.get("/components/drawer")
@jinja.hx(PathBasedTemplateSelector())
async def right_drawer_component(request: Request, db: AsyncConnection = Depends(get_db)):
    """This route serves the right drawer component for htmx requests."""
    url_parts = PathBasedTemplateSelector.parse_request_parts(request)

    match url_parts:
        case ['session', session_id]:
            from src.components.dialog.repository import SessionRepository
            session_repo = SessionRepository()
            session = await session_repo.get_by_id(db, session_id)
            return {
                'entity_id': session.id,
                'entity_type': 'session'
            }

    return {
        'data': f"Url parts: {url_parts} \n\n"
    }



@router.get("/components/navbar-notifications")
@jinja.hx('navbar-notifications.html.j2')
async def navbar_component(db: AsyncConnection = Depends(get_db)):
    """This route serves the navbar component for htmx requests."""
    from src.components.dialog.repository import SessionRepository

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

