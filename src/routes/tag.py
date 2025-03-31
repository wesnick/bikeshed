from typing import Optional
from uuid import UUID
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Form
from psycopg import AsyncConnection
from psycopg.rows import class_row
from starlette.responses import Response

from src.dependencies import get_db, get_jinja, get_tag_repository
from src.models.models import Tag
from src.repository.tag import TagRepository
from src.repository.entity_tag import EntityTagRepository
from src.service.logging import logger

router = APIRouter(prefix="/tags", tags=["tags"])
jinja = get_jinja()


from pydantic import BaseModel

class TagCreate(BaseModel):
    id: str
    path: str
    name: str
    description: Optional[str] = None

class TagUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class EntityTagRequest(BaseModel):
    entity_id: UUID
    entity_type: str
    tag_id: str
    action: str  # 'add' or 'remove'

class TagResponse(BaseModel):
    id: str
    path: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


@router.get("/")
@jinja.hx('components/tags/tag_management.html.j2', no_data=True)
async def tag_management_page():
    """Serves the main tag management page."""


@router.get("/tree")
@jinja.hx('components/tags/tag_tree.html.j2')
async def get_tag_tree(parent_path: Optional[str] = None,
                       db: AsyncConnection = Depends(get_db),
                       tag_repo: TagRepository = Depends(get_tag_repository)):
    """Fetches tags, either top-level (if parent_path is None) or children."""
    try:
        if parent_path:
            # Fetch direct children of the parent_path
            tags = await tag_repo.get_children(db, parent_path)
            # We might need parent info if we are replacing a sub-tree node
            parent_tag = await tag_repo.get_by_path(db, parent_path)
        else:
            # Fetch top-level tags (path ~ '*.') - Adjust if ltree root handling differs
            # A common pattern is to have a virtual root or fetch tags with nlevel=1
            # Let's assume get_children with a non-existent root path or similar logic fetches top level
            # For now, let's fetch tags with level 1 as top-level
            query = "SELECT * FROM tags WHERE nlevel(path) = 1 ORDER BY path"
            async with db.cursor(row_factory=class_row(Tag)) as cur:
                await cur.execute(query)
                tags = await cur.fetchall()
            parent_tag = None # No parent for top level

        logger.info(f"Fetched {len(tags)} tags for parent '{parent_path}'")
        return {"tags": tags, "parent_tag": parent_tag, "parent_path": parent_path}
    except Exception as e:
        logger.error(f"Error fetching tag tree for parent '{parent_path}': {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch tag tree")


@router.get("/create")
@jinja.hx('components/tags/tag_form.html.j2')
async def create_tag_form(parent_path: Optional[str] = None,
                          db: AsyncConnection = Depends(get_db),
                          tag_repo: TagRepository = Depends(get_tag_repository)):
    """Shows the form to create a new tag, optionally under a parent."""
    parent_tag = None
    if parent_path:
        parent_tag = await tag_repo.get_by_path(db, parent_path)
        if not parent_tag:
            raise HTTPException(status_code=404, detail="Parent tag not found")

    return {"tag": None, "parent_tag": parent_tag} # Pass None for tag as we are creating

@router.post("/")
async def create_tag(
    response: Response,
    name: str = Form(...),
    tag_id: str = Form(...), # This is the human-readable ID, also used in path
    description: Optional[str] = Form(None),
    parent_path: Optional[str] = Form(None),
    db: AsyncConnection = Depends(get_db),
    tag_repo: TagRepository = Depends(get_tag_repository)
):
    """Handles the creation of a new tag."""
    if not name or not tag_id:
        raise HTTPException(status_code=400, detail="Name and ID are required")

    # Basic validation for tag_id (ltree segment)
    import re
    if not re.match(r'^[a-z0-9_]+$', tag_id):
         raise HTTPException(status_code=400, detail="Tag ID must contain only lowercase letters, numbers, and underscores.")

    if parent_path:
        parent_tag = await tag_repo.get_by_path(db, parent_path)
        if not parent_tag:
            raise HTTPException(status_code=404, detail="Parent tag not found")
        new_path = f"{parent_path}.{tag_id}"
    else:
        new_path = tag_id # Top-level tag

    # Check if path already exists
    existing_tag = await tag_repo.get_by_path(db, new_path)
    if existing_tag:
        raise HTTPException(status_code=400, detail=f"Tag path '{new_path}' already exists.")

    new_tag = Tag(
        id=tag_id, # Using the human-readable ID here
        path=new_path,
        name=name,
        description=description
    )

    try:
        created_tag = await tag_repo.create(db, new_tag)
        logger.info(f"Created tag: {created_tag.path}")

        # Trigger an update to the specific part of the tree
        # If it's a top-level tag, target the main tree container
        # If it's a child, target the parent's children container
        if parent_path:
             # Target the children container of the parent tag
             response.headers['HX-Trigger'] = json.dumps({"sse:tag.created": {"parent_path": parent_path, "tag": created_tag.model_dump_json() }})
             # We might want to return the newly created tag item directly
             # return jinja.render('components/tags/tag_item.html.j2', {"tag": created_tag, "parent_path": parent_path})
        else:
             # Target the root tree container
             response.headers['HX-Trigger'] = json.dumps({"sse:tag.created": {"parent_path": None, "tag": created_tag.model_dump_json() }})
             # return jinja.render('components/tags/tag_item.html.j2', {"tag": created_tag, "parent_path": None})

        # For simplicity now, just trigger a general refresh or rely on SSE
        response.headers['HX-Trigger'] = json.dumps({"sse:tag.created": {"parent_path": parent_path}}) # Simplified trigger

        # Redirect back to the tag management page or return success indicator
        # Let's return an empty response with trigger for now
        return Response(status_code=201, headers=response.headers)

    except Exception as e:
        logger.error(f"Error creating tag '{new_path}': {e}")
        # Consider more specific error handling (e.g., unique constraint violation)
        raise HTTPException(status_code=500, detail=f"Failed to create tag: {e}")



# HTML component endpoints
@router.get("/components/tag-selector")
@jinja.hx('components/tags/tag_entity.html.j2')
async def tag_selector_component(
    entity_id: Optional[UUID] = None,
    entity_type: Optional[str] = None,
    db: AsyncConnection = Depends(get_db),
    tag_repo: TagRepository = Depends(get_tag_repository)
):
    """Render a tag selector component."""
    # Get all top-level tags (those without a parent)
    top_level_tags = await tag_repo.get_children(db, "root")
    
    # If entity ID and type are provided, get the entity's tags
    entity_tags = []
    if entity_id and entity_type:
        entity_tag_repo = EntityTagRepository()
        entity_tags = await entity_tag_repo.get_entity_tags(db, entity_id, entity_type)
        
        # Format tags for the tagsinput component
        entity_tags = [{"id": tag.id, "name": tag.name} for tag in entity_tags]
    
    return {
        "top_level_tags": top_level_tags,
        "entity_tags": entity_tags,
        "entity_id": entity_id,
        "entity_type": entity_type
    }

@router.get("/autocomplete")
@jinja.hx("components/tags/tag_autocomplete_results.html.j2")
async def tag_autocomplete_search(search_term: Optional[str] = None,
                                  db: AsyncConnection = Depends(get_db),
                                  tag_repo: TagRepository = Depends(get_tag_repository)):
    """Searches for tags based on the search term and returns HTML fragment."""
    if not search_term or len(search_term) < 1:
        # Optionally return popular/recent tags or an empty list
        return {"tags": []}

    try:
        tags = await tag_repo.search_by_name(db, f"%{search_term}%", limit=10)
        logger.debug(f"Autocomplete search for '{search_term}' found {len(tags)} tags.")
        return {"tags": tags}
    except Exception as e:
        logger.error(f"Error during tag autocomplete search for '{search_term}': {e}")
        # Return an empty list or an error message in the template
        return {"tags": []}


@router.post("/entity", response_class=Response) # Ensure we return Response for HX
async def manage_entity_tags(
    entity_id: UUID = Form(...),
    entity_type: str = Form(...),
    tag_id: str = Form(...),
    action: str = Form(...), # 'add' or 'remove'
    db: AsyncConnection = Depends(get_db),
    tag_repo: TagRepository = Depends(get_tag_repository) # Added tag_repo dependency
):
    """Add or remove a tag from an entity using form data and return updated component."""
    entity_tag_repo = EntityTagRepository()
    success = False
    message = ""

    try:
        if action == "add":
            # Check if tag exists before adding
            tag_to_add = await tag_repo.get_by_id(db, tag_id)
            if not tag_to_add:
                 # This case should ideally not happen if UI only allows selecting existing tags
                 logger.warning(f"Attempted to add non-existent tag '{tag_id}' to {entity_type}:{entity_id}")
                 message = f"Tag '{tag_id}' does not exist."
            else:
                success = await entity_tag_repo.add_tag_to_entity(
                    db, entity_id, entity_type, tag_id
                )
                message = f"Tag '{tag_to_add.name}' added." if success else f"Tag '{tag_to_add.name}' already present."
                if success:
                    logger.info(f"Added tag '{tag_id}' to {entity_type}:{entity_id}")


        elif action == "remove":
            # Fetch tag name for logging/message before potentially removing it
            tag_to_remove = await tag_repo.get_by_id(db, tag_id)
            tag_name = tag_to_remove.name if tag_to_remove else tag_id

            success = await entity_tag_repo.remove_tag_from_entity(
                db, entity_id, entity_type, tag_id
            )
            message = f"Tag '{tag_name}' removed." if success else f"Tag '{tag_name}' not found on entity."
            if success:
                logger.info(f"Removed tag '{tag_id}' from {entity_type}:{entity_id}")

        else:
            logger.warning(f"Invalid action '{action}' received for entity tag management.")
            message = "Invalid action specified."
            raise HTTPException(status_code=400, detail=message)

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions
        raise http_exc
    except Exception as e:
        logger.error(f"Error managing tag '{tag_id}' for {entity_type}:{entity_id} (action: {action}): {e}")
        # Return a generic error message within the component to avoid breaking the UI flow
        message = f"An error occurred while managing tag: {e}"
        # Optionally raise HTTPException(500) instead, but returning the component might be better UX
        # For now, we proceed to render the component with potentially outdated tags + error hint

    # Always re-fetch the current tags for the entity
    try:
        current_entity_tags = await entity_tag_repo.get_entity_tags(db, entity_id, entity_type)
        # Format tags for the template
        formatted_tags = [{"id": tag.id, "name": tag.name, "path": tag.path, "description": tag.description} for tag in current_entity_tags]
    except Exception as e:
        logger.error(f"Failed to re-fetch tags for {entity_type}:{entity_id} after update: {e}")
        formatted_tags = [] # Render empty if fetch fails
        message += " (Failed to refresh tag list)"


    # Render the component again with the updated (or error) state
    # Note: We pass the original entity_id and entity_type back to the template
    context = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "entity_tags": formatted_tags,
        "message": message, # Optionally display a status message
        "success": success and action in ['add', 'remove'] # Indicate overall success of the intended action
    }
    return jinja.template_response("components/tags/tag_entity.html.j2", context)


