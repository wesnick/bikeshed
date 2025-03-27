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
from src.service import tag_service
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



# Tag CRUD endpoints
@router.get("/api", response_model=List[TagResponse])
async def get_tags(
    path_prefix: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncConnection = Depends(get_db)
):
    """Get tags, optionally filtered by path prefix or search term."""
    if path_prefix:
        # Get children of a path
        tags = await tag_service.get_tag_children(db, path_prefix)
    elif search:
        # Search by name
        tags = await tag_service.search_tags(db, search, limit)
    else:
        # Get all tags with limit
        tags = await tag_service.tag_repo.get_all(db, limit=limit)
    
    return tags

@router.get("/api/{tag_id}", response_model=TagResponse)
async def get_tag(tag_id: str, db: AsyncConnection = Depends(get_db)):
    """Get a tag by ID."""
    tag = await tag_service.get_tag(db, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag

@router.post("/api", response_model=TagResponse)
async def create_tag(tag_data: TagCreate, db: AsyncConnection = Depends(get_db)):
    """Create a new tag."""
    # Check if tag with this ID already exists
    existing_tag = await tag_service.get_tag(db, tag_data.id)
    if existing_tag:
        raise HTTPException(status_code=400, detail="Tag with this ID already exists")
    
    # Check if tag with this path already exists
    existing_path = await tag_service.get_tag_by_path(db, tag_data.path)
    if existing_path:
        raise HTTPException(status_code=400, detail="Tag with this path already exists")
    
    # Create the tag
    tag = Tag(
        id=tag_data.id,
        path=tag_data.path,
        name=tag_data.name,
        description=tag_data.description,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    created_tag = await tag_service.create_tag(db, tag)
    return created_tag

@router.put("/api/{tag_id}", response_model=TagResponse)
async def update_tag(tag_id: str, tag_data: TagUpdate, db: AsyncConnection = Depends(get_db)):
    """Update an existing tag."""
    # Check if tag exists
    existing_tag = await tag_service.get_tag(db, tag_id)
    if not existing_tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    # Prepare update data
    update_data = tag_data.model_dump(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = datetime.now()
    
    # Update the tag
    updated_tag = await tag_service.update_tag(db, tag_id, update_data)
    return updated_tag

@router.delete("/api/{tag_id}", response_model=bool)
async def delete_tag(tag_id: str, db: AsyncConnection = Depends(get_db)):
    """Delete a tag."""
    # Check if tag exists
    existing_tag = await tag_service.get_tag(db, tag_id)
    if not existing_tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    # Delete the tag
    success = await tag_service.delete_tag(db, tag_id)
    return success

# Entity-tag relationship endpoints
@router.post("/api/entity", response_model=bool)
async def add_tag_to_entity(request: EntityTagRequest, db: AsyncConnection = Depends(get_db)):
    """Add a tag to an entity."""
    success = await tag_service.add_tag_to_entity(db, request.entity_id, request.entity_type, request.tag_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tag not found or relationship already exists")
    return success

@router.delete("/api/entity", response_model=bool)
async def remove_tag_from_entity(request: EntityTagRequest, db: AsyncConnection = Depends(get_db)):
    """Remove a tag from an entity."""
    success = await tag_service.remove_tag_from_entity(db, request.entity_id, request.entity_type, request.tag_id)
    if not success:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return success

@router.get("/api/entity/{entity_type}/{entity_id}", response_model=List[TagResponse])
async def get_entity_tags(entity_type: str, entity_id: UUID, db: AsyncConnection = Depends(get_db)):
    """Get all tags for an entity."""
    tags = await tag_service.get_entity_tags(db, entity_id, entity_type)
    return tags

# HTML component endpoints
@router.get("/components/tag-selector")
@get_jinja().hx('components/tag_selector.html.j2')
async def tag_selector_component(
    entity_id: Optional[UUID] = None,
    entity_type: Optional[str] = None,
    db: AsyncConnection = Depends(get_db)
):
    """Render a tag selector component."""
    # Get all top-level tags (those without a parent)
    top_level_tags = await tag_service.tag_repo.get_children(db, "root")
    
    # If entity ID and type are provided, get the entity's tags
    entity_tags = []
    if entity_id and entity_type:
        entity_tags = await tag_service.get_entity_tags(db, entity_id, entity_type)
    
    return {
        "top_level_tags": top_level_tags,
        "entity_tags": entity_tags,
        "entity_id": entity_id,
        "entity_type": entity_type
    }

@router.get("/components/entity-tags")
@get_jinja().hx('components/entity_tags.html.j2')
async def entity_tags_component(
    entity_id: UUID,
    entity_type: str,
    db: AsyncConnection = Depends(get_db)
):
    """Render the tags for an entity."""
    tags = await tag_service.get_entity_tags(db, entity_id, entity_type)
    
    return {
        "tags": tags,
        "entity_id": entity_id,
        "entity_type": entity_type
    }
