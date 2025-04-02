from fastapi import APIRouter, Request, Depends
from psycopg import AsyncConnection

from src.service.user_state import UserStateService
from src.dependencies import get_user_state_service

from src.core.models import DialogStatus
from src.core.registry import Registry
from src.dependencies import get_db, get_jinja, get_registry
from src.components.repositories import dialog_repository

import uuid



router = APIRouter(tags=["navbar"])

jinja = get_jinja("src/components/navigation/templates")



@router.get("/components/left-sidebar")
@jinja.hx('left_sidebar.html.j2')
async def left_sidebar_component(db: AsyncConnection = Depends(get_db), registry: Registry = Depends(get_registry)) -> dict:
    """This route serves the left sidebar component for htmx requests."""
    dialogs = await dialog_repository.get_recent_dialogs(db)

    dialog_templates = registry.dialog_templates

    return {
        "flows": [],
        "dialogs": dialogs,
        "tools": [],
        "prompts": [],
        "dialog_templates": dialog_templates,
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
            case 'dialog':
                # test if uuid
                try:
                    uuid.UUID(url_parts[1])
                    return 'dialog_context.html.j2'
                except ValueError:
                    pass

        return 'empty.html.j2'

@router.get("/components/drawer")
@jinja.hx(PathBasedTemplateSelector())
async def right_drawer_component(request: Request, db: AsyncConnection = Depends(get_db)):
    """This route serves the right drawer component for htmx requests."""
    url_parts = PathBasedTemplateSelector.parse_request_parts(request)

    match url_parts:
        case ['dialog', dialog_id]:
            from src.components.dialog.repository import DialogRepository
            dialog_repo = DialogRepository()
            dialog = await dialog_repo.get_by_id(db, dialog_id)
            return {
                'entity_id': dialog.id,
                'entity_type': 'dialog'
            }

    return {
        'data': f"Url parts: {url_parts} \n\n"
    }



@router.get("/components/navbar-notifications")
@jinja.hx('navbar-notifications.html.j2')
async def navbar_component(db: AsyncConnection = Depends(get_db)):
    """This route serves the navbar component for htmx requests."""
    from src.components.dialog.repository import DialogRepository

    dialog_repo = DialogRepository()
    active_dialogs = await dialog_repo.get_active_dialogs(db)

    running_dialogs = [s for s in active_dialogs if s.status == DialogStatus.RUNNING]
    waiting_dialogs = [s for s in active_dialogs if s.status == DialogStatus.WAITING_FOR_INPUT]

    return {
        'total_running': len(running_dialogs),
        'total_waiting': len(waiting_dialogs),
        'running_dialogs': running_dialogs,
        'waiting_dialogs': waiting_dialogs
    }

