from typing import Optional
from fastapi import APIRouter, Depends
from psycopg import AsyncConnection
from pydantic import BaseModel, model_validator

from src.dependencies import get_db, get_jinja, get_user_state_service, enqueue_job
from src.components.repositories import root_repository
from src.core.models import Root
from src.service.user_state import UserStateService
from src.service.logging import logger
from src.utils.file_tree import build_file_tree

router = APIRouter(prefix="/root", tags=["roots"])
jinja = get_jinja("src/components/root/templates")

## Request Models
class RootSelectRequest(BaseModel):
    root_uri: str

class AddRootRequest(BaseModel):
    path_or_uri: str
    name: Optional[str] = None


    @model_validator(mode='after')
    def validate_path_or_uri(self):
        v = self.path_or_uri.strip()
        if not v:
            raise ValueError("Path or URI cannot be empty")
        # @TODO: validate we get a valid git or local path
        # if not v.startswith(('https://', 'http://', 'git@')) and not os.path.exists(v):
        #     logger.warning(f"Provided path does not seem to exist locally: {v}")
            # Consider raising ValueError if strict local path validation is needed immediately
            # raise ValueError(f"Local path does not exist: {v}")
        # Basic check for Git URI (very simplistic)
        # elif v.startswith(('https://', 'http://', 'git@')) and not v.endswith('.git'):
            # logger.warning(f"Provided URI might not be a standard Git URI: {v}")
            # Consider adding more robust URI validation if needed
        return self


async def _render_management_page(db: AsyncConnection, user_state_service: UserStateService):
    """Helper function to fetch data and render the management page."""

    roots = await root_repository.get_all(db)
    selected_roots = user_state_service.get('selected_roots', default=[])
    return {
        'roots': roots,
        'selected_roots': selected_roots
    }


@router.post("/select")
@jinja.hx('root_selector.html.j2')
async def select_root(root_select: RootSelectRequest,
                      db: AsyncConnection = Depends(get_db),
                      user_state_service: UserStateService = Depends(get_user_state_service)
                     ):
    """Select a root as the current working root."""
    selected_root_obj = await root_repository.get_by_uri(db, root_select.root_uri)

    # Get the current list of selected roots
    current_selected_roots = user_state_service.get('selected_roots', default=[])

    if selected_root_obj:
        if selected_root_obj.uri not in current_selected_roots:
            current_selected_roots.append(selected_root_obj.uri)
            user_state_service.set('selected_roots', current_selected_roots)

    return await _render_management_page(db, user_state_service)


@router.post("/deselect")
@jinja.hx('root_selector.html.j2')
async def deselect_root(root_deselect: RootSelectRequest,
                        db: AsyncConnection = Depends(get_db),
                        user_state_service: UserStateService = Depends(get_user_state_service)
                       ):
    """Deselect a root from the current working set."""

    # Get the current list of selected roots
    current_selected_roots = user_state_service.get('selected_roots', default=[])

    # Remove the root if it exists in the list
    if root_deselect.root_uri in current_selected_roots:
        current_selected_roots.remove(root_deselect.root_uri)
        user_state_service.set('selected_roots', current_selected_roots)

    return await _render_management_page(db, user_state_service)

@router.get("/manage")
@jinja.hx('overview.html.j2')
async def get_root_management_page(
    db: AsyncConnection = Depends(get_db),
    user_state_service: UserStateService = Depends(get_user_state_service)
):
    """Display the root management page."""
    return await _render_management_page(db, user_state_service)


@router.get("")
@jinja.hx('root_view.html.j2')
async def view_root(root_uri: str, db: AsyncConnection = Depends(get_db)):
    """This route serves the root view component for htmx requests."""
    from src.service.logging import logger
    logger.warning(f"Root URI: {root_uri}")

    root = await root_repository.get_with_files(db, root_uri)

    if not root:
        return {"error": "Root not found"}

    return {
        'root': root,
        'tree': build_file_tree(root.files),
        'error': None,
    }


@router.get("-selector")
@jinja.hx('root_selector.html.j2')
async def root_selector_component(
    db: AsyncConnection = Depends(get_db),
    user_state_service: UserStateService = Depends(get_user_state_service) # Add this dependency
):
    """This route serves the root selector component for htmx requests."""

    from src.components.root.repository import RootRepository

    root_repo = RootRepository()
    roots = await root_repo.get_all(db)
    selected_roots = user_state_service.get('selected_roots', default=[])

    return {
        'roots': roots,
        'selected_roots': selected_roots
    }

@router.post("/add")
@jinja.hx('overview.html.j2')
async def add_root(
    add_root_req: AddRootRequest,
    db: AsyncConnection = Depends(get_db),
    user_state_service: UserStateService = Depends(get_user_state_service)):
    """Add a new root (directory or Git repository) and scan it."""

    # Check if root with this URI already exists
    existing_root = await root_repository.get_by_uri(db, add_root_req.path_or_uri)
    if existing_root:
        logger.warning(f"Root with URI '{add_root_req.path_or_uri}' already exists.")
        # Re-render the page, potentially with an error message
        page_data = await _render_management_page(db, user_state_service)
        page_data['error_message'] = f"Root with URI '{add_root_req.path_or_uri}' already exists."
        # How to pass error message to template? Add it to the context.
        # Need to update template to display 'error_message' if present.
        # For now, just log and proceed to render without adding.
        return page_data

    try:
        new_root = Root(uri=add_root_req.path_or_uri)
        created_root = await root_repository.create(db, new_root) # Assuming create returns the created object
        logger.info(f"Created root entry for {created_root.uri}")
        job_id = await enqueue_job('process_root', directory_path=add_root_req.path_or_uri)
        logger.warning(f"Create job {job_id}")


    except Exception as e:
        logger.error(f"Failed to add or scan root '{add_root_req.path_or_uri}': {e}")
        # Re-render the page with an error
        page_data = await _render_management_page(db, user_state_service)
        page_data['error_message'] = f"Failed to add root: {e}"
        # Need to update template to display 'error_message'
        return page_data


    # Re-render the management page with the updated list
    return await _render_management_page(db, user_state_service)

# TODO: Add endpoint for deleting roots
# TODO: Add endpoint for re-scanning roots
