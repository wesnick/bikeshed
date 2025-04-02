from typing import Optional
from uuid import UUID
import json

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection
from psycopg.rows import class_row
from starlette.responses import Response
from pydantic import BaseModel, Field

from src.dependencies import get_db, get_jinja
from src.core.models import Tag
from src.components.repositories import tag_repository, entity_tag_repository
from src.service.logging import logger

router = APIRouter(prefix="/tags", tags=["tags"])
jinja = get_jinja("src/components/tag/templates")


class TagCreateRequest(BaseModel):
    name: str
    tag_id: str = Field(..., pattern=r'^[a-z0-9_]+$') # Use Field for validation
    description: Optional[str] = None
    parent_path: Optional[str] = None

class EntityTagRequest(BaseModel):
    entity_id: UUID
    entity_type: str

@router.get("/")
@jinja.hx('tag_management.html.j2', no_data=True)
async def tag_management_page():
    """Serves the main tag management page."""


@router.get("/tree")
@jinja.hx('tag_tree.html.j2')
async def get_tag_tree(parent_path: Optional[str] = None,
                       db: AsyncConnection = Depends(get_db)):
    """Fetches tags, either top-level (if parent_path is None) or children."""
    try:
        if parent_path:
            # Fetch direct children of the parent_path
            tags = await tag_repository.get_children(db, parent_path)
            # We might need parent info if we are replacing a sub-tree node
            parent_tag = await tag_repository.get_by_path(db, parent_path)
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
@jinja.hx('tag_form.html.j2')
async def create_tag_form(parent_path: Optional[str] = None,
                          db: AsyncConnection = Depends(get_db)):
    """Shows the form to create a new tag, optionally under a parent."""
    parent_tag = None
    if parent_path:
        parent_tag = await tag_repository.get_by_path(db, parent_path)
        if not parent_tag:
            raise HTTPException(status_code=404, detail="Parent tag not found")

    return {"tag": None, "parent_tag": parent_tag} # Pass None for tag as we are creating

@router.post("/")
async def create_tag(
    tag_data: TagCreateRequest,
    response: Response,
    db: AsyncConnection = Depends(get_db)
):
    """Handles the creation of a new tag using JSON data."""
    # Validation is handled by Pydantic based on TagCreateRequest definition

    if tag_data.parent_path:
        parent_tag = await tag_repository.get_by_path(db, tag_data.parent_path)
        if not parent_tag:
            raise HTTPException(status_code=404, detail="Parent tag not found")
        new_path = f"{tag_data.parent_path}.{tag_data.tag_id}"
    else:
        new_path = tag_data.tag_id # Top-level tag

    # Check if path already exists
    existing_tag = await tag_repository.get_by_path(db, new_path)
    if existing_tag:
        raise HTTPException(status_code=400, detail=f"Tag path '{new_path}' already exists.")

    new_tag = Tag(
        id=tag_data.tag_id, # Using the human-readable ID here
        path=new_path,
        name=tag_data.name,
        description=tag_data.description
    )

    try:
        created_tag = await tag_repository.create(db, new_tag)
        logger.info(f"Created tag: {created_tag.path}")

        # Trigger an update to the specific part of the tree
        # If it's a top-level tag, target the main tree container
        # If it's a child, target the parent's children container
        parent_path_for_trigger = tag_data.parent_path # Use the value from the request data
        if parent_path_for_trigger:
             # Target the children container of the parent tag
             response.headers['HX-Trigger'] = json.dumps({"sse:tag.created": {"parent_path": parent_path_for_trigger, "tag": created_tag.model_dump_json() }})
             # We might want to return the newly created tag item directly
             # return jinja.render('components/tags/tag_item.html.j2', {"tag": created_tag, "parent_path": parent_path_for_trigger})
        else:
             # Target the root tree container
             response.headers['HX-Trigger'] = json.dumps({"sse:tag.created": {"parent_path": None, "tag": created_tag.model_dump_json() }})
             # return jinja.render('components/tags/tag_item.html.j2', {"tag": created_tag, "parent_path": None})

        # For simplicity now, just trigger a general refresh or rely on SSE
        response.headers['HX-Trigger'] = json.dumps({"sse:tag.created": {"parent_path": parent_path_for_trigger}}) # Simplified trigger

        # Redirect back to the tag management page or return success indicator
        # Let's return an empty response with trigger for now
        return Response(status_code=201, headers=response.headers)

    except Exception as e:
        logger.error(f"Error creating tag '{new_path}': {e}")
        # Consider more specific error handling (e.g., unique constraint violation)
        raise HTTPException(status_code=500, detail=f"Failed to create tag: {e}")



# HTML component endpoints
@router.get("/components/tag-selector")
@jinja.hx('tag_entity.html.j2')
async def tag_selector_component(
    entity_id: Optional[UUID] = None,
    entity_type: Optional[str] = None,
    db: AsyncConnection = Depends(get_db)
):
    """Render a tag selector component."""
    # Get all top-level tags (those without a parent)
    top_level_tags = await tag_repository.get_children(db, "root")

    # If entity ID and type are provided, get the entity's tags
    entity_tags = []
    if entity_id and entity_type:
        entity_tags = await entity_tag_repository.get_entity_tags(db, entity_id, entity_type)

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
                                  db: AsyncConnection = Depends(get_db)):
    """Searches for tags based on the search term and returns HTML fragment."""
    if not search_term or len(search_term) < 1:
        # Optionally return popular/recent tags or an empty list
        return {"tags": []}

    try:
        tags = await tag_repository.search_by_name(db, f"%{search_term}%", limit=10)
        logger.debug(f"Autocomplete search for '{search_term}' found {len(tags)} tags.")
        return {"tags": tags}
    except Exception as e:
        logger.error(f"Error during tag autocomplete search for '{search_term}': {e}")
        # Return an empty list or an error message in the template
        return {"tags": []}


@router.post("/entity")
@jinja.hx("components/tags/tag_entity.html.j2")
async def manage_entity_tags(
    tag_entity: EntityTagRequest,
    db: AsyncConnection = Depends(get_db)):
    """Add or remove a tag from an entity using form data and return updated component."""
    success = False
    message = ""

    try:
        if tag_entity.action == "add":
            # Check if tag exists before adding
            tag_to_add = await tag_repository.get_by_id(db, tag_entity.tag_id)
            if not tag_to_add:
                 # This case should ideally not happen if UI only allows selecting existing tags
                 logger.warning(f"Attempted to add non-existent tag '{tag_entity.tag_id}' to {tag_entity.entity_type}:{tag_entity.entity_id}")
                 message = f"Tag '{tag_entity.tag_id}' does not exist."
            else:
                success = await entity_tag_repository.add_tag_to_entity(
                    db, tag_entity.entity_id, tag_entity.entity_type, tag_entity.tag_id
                )
                message = f"Tag '{tag_to_add.name}' added." if success else f"Tag '{tag_to_add.name}' already present."
                if success:
                    logger.info(f"Added tag '{tag_entity.tag_id}' to {tag_entity.entity_type}:{tag_entity.entity_id}")


        elif tag_entity.action == "remove":
            # Fetch tag name for logging/message before potentially removing it
            tag_to_remove = await tag_repository.get_by_id(db, tag_entity.tag_id)
            tag_name = tag_to_remove.name if tag_to_remove else tag_entity.tag_id

            success = await entity_tag_repository.remove_tag_from_entity(
                db, tag_entity.entity_id, tag_entity.entity_type, tag_entity.tag_id
            )
            message = f"Tag '{tag_name}' removed." if success else f"Tag '{tag_name}' not found on entity."
            if success:
                logger.info(f"Removed tag '{tag_entity.tag_id}' from {tag_entity.entity_type}:{tag_entity.entity_id}")

        else:
            logger.warning(f"Invalid action '{tag_entity.action}' received for entity tag management.")
            message = "Invalid action specified."
            raise HTTPException(status_code=400, detail=message)

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions
        raise http_exc
    except Exception as e:
        logger.error(f"Error managing tag '{tag_entity.tag_id}' for {tag_entity.entity_type}:{tag_entity.entity_id} (action: {tag_entity.action}): {e}")
        # Return a generic error message within the component to avoid breaking the UI flow
        message = f"An error occurred while managing tag: {e}"
        # Optionally raise HTTPException(500) instead, but returning the component might be better UX
        # For now, we proceed to render the component with potentially outdated tags + error hint

    # Always re-fetch the current tags for the entity
    try:
        current_entity_tags = await entity_tag_repository.get_entity_tags(db, tag_entity.entity_id, tag_entity.entity_type)
        # Format tags for the template
        formatted_tags = [{"id": tag.id, "name": tag.name, "path": tag.path, "description": tag.description} for tag in current_entity_tags]
    except Exception as e:
        logger.error(f"Failed to re-fetch tags for {tag_entity.entity_type}:{tag_entity.entity_id} after update: {e}")
        formatted_tags = [] # Render empty if fetch fails
        message += " (Failed to refresh tag list)"


    return {
        "entity_id": tag_entity.entity_id,
        "entity_type": tag_entity.entity_type,
        "entity_tags": formatted_tags,
        "message": message,
        "success": success and tag_entity.action in ['add', 'remove']
    }
