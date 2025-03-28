from typing import List, Optional
from uuid import UUID
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Form
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
    
    return {
        "top_level_tags": top_level_tags,
        "entity_tags": entity_tags,
        "entity_id": entity_id,
        "entity_type": entity_type
    }

@router.get("/autocomplete/{search_term}")
async def entity_tags_component(search_term: str,
                                db: AsyncConnection = Depends(get_db),
                                tag_repo: TagRepository = Depends(get_tag_repository)):

    terms = await tag_repo.search_by_name(db, search_term)

    res = [{'id': term.id, 'name': term.name} for term in terms]

    from src.service.logging import logger
    logger.error(f"res: {res}")

    return res


