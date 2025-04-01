import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg import AsyncConnection
from pydantic import BaseModel, validator

from src.dependencies import get_db, get_jinja, get_user_state_service, get_root_repository
from src.repository.root import RootRepository, Root
from src.service.user_state import UserStateService
from src.core.roots.scanner import FileScanner # Assuming FileScanner is here
from src.service.logging import logger

router = APIRouter(tags=["root_management"])
jinja = get_jinja()

class AddRootRequest(BaseModel):
    path_or_uri: str
    name: Optional[str] = None

    @validator('path_or_uri')
    def validate_path_or_uri(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Path or URI cannot be empty")
        # Basic check for local path existence (can be improved)
        # if not v.startswith(('https://', 'http://', 'git@')) and not os.path.exists(v):
        #     logger.warning(f"Provided path does not seem to exist locally: {v}")
            # Consider raising ValueError if strict local path validation is needed immediately
            # raise ValueError(f"Local path does not exist: {v}")
        # Basic check for Git URI (very simplistic)
        # elif v.startswith(('https://', 'http://', 'git@')) and not v.endswith('.git'):
            # logger.warning(f"Provided URI might not be a standard Git URI: {v}")
            # Consider adding more robust URI validation if needed
        return v


async def _render_management_page(db: AsyncConnection, user_state_service: UserStateService):
    """Helper function to fetch data and render the management page."""
    root_repo: RootRepository = get_root_repository() # Get repo instance
    roots = await root_repo.get_all(db)
    selected_roots = user_state_service.get('selected_roots', default=[])
    return {
        'roots': roots,
        'selected_roots': selected_roots
    }

@router.get("/manage")
@jinja.hx('pages/root_management.html.j2', target_id="dashboard")
async def get_root_management_page(
    db: AsyncConnection = Depends(get_db),
    user_state_service: UserStateService = Depends(get_user_state_service)
):
    """Display the root management page."""
    return await _render_management_page(db, user_state_service)


@router.post("/add")
@jinja.hx('pages/root_management.html.j2', target_id="dashboard")
async def add_root(
    request: AddRootRequest,
    db: AsyncConnection = Depends(get_db),
    user_state_service: UserStateService = Depends(get_user_state_service)
    # Inject RootRepository directly if FileScanner isn't needed or complex to inject
    # root_repo: RootRepository = Depends(get_root_repository)
):
    """Add a new root (directory or Git repository) and scan it."""
    # For now, directly instantiate FileScanner or call repo methods.
    # A dedicated dependency/service might be better long-term.
    root_repo: RootRepository = get_root_repository()

    # Check if root with this URI already exists
    existing_root = await root_repo.get_by_uri(db, request.path_or_uri)
    if existing_root:
        logger.warning(f"Root with URI '{request.path_or_uri}' already exists.")
        # Re-render the page, potentially with an error message
        page_data = await _render_management_page(db, user_state_service)
        page_data['error_message'] = f"Root with URI '{request.path_or_uri}' already exists."
        # How to pass error message to template? Add it to the context.
        # Need to update template to display 'error_message' if present.
        # For now, just log and proceed to render without adding.
        return page_data


    # Using FileScanner (requires get_db callable and RootRepository instance)
    # This structure assumes get_db returns a callable that yields a connection manager
    async def get_db_conn_callable():
         async with db as conn: # Use the existing connection from Depends(get_db)
             yield conn

    # Need to adapt FileScanner or its usage if get_db provides the connection directly
    # Option 1: Modify FileScanner to accept a connection directly (if feasible)
    # Option 2: Create the scanner and pass the connection when calling scan methods
    # Option 3: Use RootRepository methods if they handle scanning upon creation

    # Let's assume RootRepository handles basic creation and FileScanner is for scanning existing ones
    # Or simplify: Add Root first, then trigger scan (maybe async later)

    try:
        # Simplified: Create Root entry first
        new_root = Root(uri=request.path_or_uri, name=request.name)
        created_root = await root_repo.create(db, new_root) # Assuming create returns the created object
        logger.info(f"Created root entry for {created_root.uri}")

        # Now, initiate scanning (synchronously for now)
        # This part needs the FileScanner logic integrated.
        # Let's placeholder the scanning logic for now.
        # TODO: Integrate actual scanning logic here, potentially using FileScanner
        logger.info(f"Scanning for root {created_root.uri} needs to be implemented.")
        # Example placeholder call (replace with actual implementation):
        # file_scanner = FileScanner(get_db=get_db_conn_callable, root_repo=root_repo)
        # await file_scanner.scan_existing_root(created_root) # Need a method like this

    except Exception as e:
        logger.error(f"Failed to add or scan root '{request.path_or_uri}': {e}")
        # Re-render the page with an error
        page_data = await _render_management_page(db, user_state_service)
        page_data['error_message'] = f"Failed to add root: {e}"
        # Need to update template to display 'error_message'
        return page_data


    # Re-render the management page with the updated list
    return await _render_management_page(db, user_state_service)

# TODO: Add endpoint for deleting roots
# TODO: Add endpoint for re-scanning roots
