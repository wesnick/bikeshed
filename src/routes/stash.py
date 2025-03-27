from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from psycopg import AsyncConnection
from datetime import datetime

from src.models.models import Stash, StashItem
from src.dependencies import get_db, get_jinja
from src.service.stash_service import StashService

router = APIRouter(prefix="/stashes", tags=["stashes"])
stash_service = StashService()
jinja = get_jinja()

# Pydantic models for request/response
from pydantic import BaseModel

class StashCreate(BaseModel):
    name: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class StashUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class StashItemCreate(BaseModel):
    type: str
    content: str
    metadata: Optional[Dict[str, Any]] = None

class EntityStashRequest(BaseModel):
    entity_id: UUID
    entity_type: str
    stash_id: UUID

class StashResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    items: List[StashItem]
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None

# Stash CRUD endpoints
@router.get("", response_model=List[StashResponse])
async def get_stashes(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncConnection = Depends(get_db)
):
    """Get recent stashes."""
    stashes = await stash_service.get_recent_stashes(db, limit)
    return stashes

@router.get("/{stash_id}", response_model=StashResponse)
async def get_stash(stash_id: UUID, db: AsyncConnection = Depends(get_db)):
    """Get a stash by ID."""
    stash = await stash_service.get_stash(db, stash_id)
    if not stash:
        raise HTTPException(status_code=404, detail="Stash not found")
    return stash

@router.post("", response_model=StashResponse)
async def create_stash(stash_data: StashCreate, request: Request, db: AsyncConnection = Depends(get_db)):
    """Create a new stash."""
    # Check if stash with this name already exists
    existing_stash = await stash_service.get_stash_by_name(db, stash_data.name)
    if existing_stash:
        raise HTTPException(status_code=400, detail="Stash with this name already exists")
    
    # Create the stash
    stash = Stash(
        name=stash_data.name,
        description=stash_data.description,
        items=[],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata=stash_data.metadata
    )
    
    created_stash = await stash_service.create_stash(db, stash)
    
    # If this is an HTMX request, redirect to the stash list
    if "HX-Request" in request.headers:
        return jinja.TemplateResponse("components/stash/list.html.j2", {
            "request": request,
            "stashes": await stash_service.get_recent_stashes(db)
        })
    
    return created_stash

@router.put("/{stash_id}", response_model=StashResponse)
async def update_stash(stash_id: UUID, stash_data: StashUpdate, request: Request, db: AsyncConnection = Depends(get_db)):
    """Update an existing stash."""
    # Check if stash exists
    existing_stash = await stash_service.get_stash(db, stash_id)
    if not existing_stash:
        raise HTTPException(status_code=404, detail="Stash not found")
    
    # Prepare update data
    update_data = stash_data.model_dump(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = datetime.now()
    
    # Update the stash
    updated_stash = await stash_service.update_stash(db, stash_id, update_data)
    
    # If this is an HTMX request, return the stash detail view
    if "HX-Request" in request.headers:
        return jinja.TemplateResponse("components/stash/detail.html.j2", {
            "request": request,
            "stash": updated_stash
        })
    
    return updated_stash

@router.delete("/{stash_id}", response_model=bool)
async def delete_stash(stash_id: UUID, request: Request, db: AsyncConnection = Depends(get_db)):
    """Delete a stash."""
    # Check if stash exists
    existing_stash = await stash_service.get_stash(db, stash_id)
    if not existing_stash:
        raise HTTPException(status_code=404, detail="Stash not found")
    
    # Delete the stash
    success = await stash_service.delete_stash(db, stash_id)
    
    # If this is an HTMX request, return the stash list view
    if "HX-Request" in request.headers:
        return jinja.TemplateResponse("components/stash/list.html.j2", {
            "request": request,
            "stashes": await stash_service.get_recent_stashes(db)
        })
    
    return success

# Stash item endpoints
@router.post("/{stash_id}/items", response_model=StashResponse)
async def add_item_to_stash(stash_id: UUID, item_data: StashItemCreate, request: Request, db: AsyncConnection = Depends(get_db)):
    """Add an item to a stash."""
    # Check if stash exists
    existing_stash = await stash_service.get_stash(db, stash_id)
    if not existing_stash:
        raise HTTPException(status_code=404, detail="Stash not found")
    
    # Create the item
    item = StashItem(
        type=item_data.type,
        content=item_data.content,
        metadata=item_data.metadata
    )
    
    # Add the item to the stash
    updated_stash = await stash_service.add_item_to_stash(db, stash_id, item)
    
    # If this is an HTMX request, return just the items component
    if "HX-Request" in request.headers:
        return jinja.TemplateResponse("components/stash/items.html.j2", {
            "request": request,
            "stash": updated_stash
        })
    
    return updated_stash

@router.delete("/{stash_id}/items/{item_index}", response_model=StashResponse)
async def remove_item_from_stash(stash_id: UUID, item_index: int, request: Request, db: AsyncConnection = Depends(get_db)):
    """Remove an item from a stash by its index."""
    # Check if stash exists
    existing_stash = await stash_service.get_stash(db, stash_id)
    if not existing_stash:
        raise HTTPException(status_code=404, detail="Stash not found")
    
    # Check if item index is valid
    if item_index < 0 or item_index >= len(existing_stash.items):
        raise HTTPException(status_code=400, detail="Invalid item index")
    
    # Remove the item from the stash
    updated_stash = await stash_service.remove_item_from_stash(db, stash_id, item_index)
    
    # If this is an HTMX request, return just the items component
    if "HX-Request" in request.headers:
        return jinja.TemplateResponse("components/stash/items.html.j2", {
            "request": request,
            "stash": updated_stash
        })
    
    return updated_stash

# Entity-stash relationship endpoints
@router.post("/entity", response_model=bool)
async def add_stash_to_entity(request: EntityStashRequest, db: AsyncConnection = Depends(get_db)):
    """Add a stash to an entity."""
    success = await stash_service.add_stash_to_entity(db, request.entity_id, request.entity_type, request.stash_id)
    if not success:
        raise HTTPException(status_code=404, detail="Stash not found or relationship already exists")
    return success

@router.delete("/entity", response_model=bool)
async def remove_stash_from_entity(request: EntityStashRequest, db: AsyncConnection = Depends(get_db)):
    """Remove a stash from an entity."""
    success = await stash_service.remove_stash_from_entity(db, request.entity_id, request.entity_type, request.stash_id)
    if not success:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return success

@router.get("/entity/{entity_type}/{entity_id}", response_model=List[StashResponse])
async def get_entity_stashes(entity_type: str, entity_id: UUID, db: AsyncConnection = Depends(get_db)):
    """Get all stashes for an entity."""
    stashes = await stash_service.get_entity_stashes(db, entity_id, entity_type)
    return stashes

# HTML component endpoints
@router.get("/components/stash-selector")
@jinja.hx('components/stash/stash_selector.html.j2')
async def stash_selector_component(
    entity_id: Optional[UUID] = None,
    entity_type: Optional[str] = None,
    db: AsyncConnection = Depends(get_db)
):
    """Render a stash selector component."""
    # Get recent stashes
    stashes = await stash_service.get_recent_stashes(db, limit=20)
    
    # If entity ID and type are provided, get the entity's stashes
    entity_stashes = []
    if entity_id and entity_type:
        entity_stashes = await stash_service.get_entity_stashes(db, entity_id, entity_type)
    
    return {
        "stashes": stashes,
        "entity_stashes": entity_stashes,
        "entity_id": entity_id,
        "entity_type": entity_type
    }

@router.get("/components/entity-stashes")
@jinja.hx('components/stash/entity_stashes.html.j2')
async def entity_stashes_component(
    entity_id: UUID,
    entity_type: str,
    db: AsyncConnection = Depends(get_db)
):
    """Render the stashes for an entity."""
    stashes = await stash_service.get_entity_stashes(db, entity_id, entity_type)
    
    return {
        "stashes": stashes,
        "entity_id": entity_id,
        "entity_type": entity_type
    }
