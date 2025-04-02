import json
from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from psycopg import AsyncConnection
from datetime import datetime

from src.core.models import Stash, StashItem
from src.dependencies import get_db, get_jinja
from src.components.repositories import stash_repository, entity_stash_repository

router = APIRouter(prefix="/stashes", tags=["stashes"])
jinja = get_jinja("src/components/stash/templates")

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
@router.get("")
@jinja.hx('list.html.j2')
async def get_stashes(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncConnection = Depends(get_db)
):
    """Get recent stashes."""
    stashes = await stash_repository.get_recent(db, limit)
    return {"stashes": stashes}

@router.get("/create")
@jinja.hx('create.html.j2')
async def create_stash_form():
    """Render the create stash form."""
    return {}


@router.get("/{stash_id}")
@jinja.hx('detail.html.j2')
async def get_stash_detail(stash_id: UUID, db: AsyncConnection = Depends(get_db)):
    """Get a stash by ID."""
    stash = await stash_repository.get_by_id(db, stash_id)
    if not stash:
        raise HTTPException(status_code=404, detail="Stash not found")
    return {"stash": stash}


@router.get("/{stash_id}/edit")
@jinja.hx('edit.html.j2')
async def edit_stash_form(stash_id: UUID, db: AsyncConnection = Depends(get_db)):
    """Render the edit stash form."""
    stash = await stash_repository.get_by_id(db, stash_id)
    if not stash:
        raise HTTPException(status_code=404, detail="Stash not found")
    return {"stash": stash}

@router.get("/{stash_id}/items")
@jinja.hx('items.html.j2')
async def get_stash_items(stash_id: UUID, db: AsyncConnection = Depends(get_db)):
    """Get items for a stash."""
    stash = await stash_repository.get_by_id(db, stash_id)
    if not stash:
        raise HTTPException(status_code=404, detail="Stash not found")
    return {"stash": stash}

@router.get("/{stash_id}/add-item")
@jinja.hx('add_item.html.j2')
async def add_item_form(stash_id: UUID, db: AsyncConnection = Depends(get_db)):
    """Render the add item form."""
    stash = await stash_repository.get_by_id(db, stash_id)
    if not stash:
        raise HTTPException(status_code=404, detail="Stash not found")
    return {"stash": stash}


@router.post("")
@jinja.hx('detail.html.j2')
async def create_stash(stash_data: StashCreate, request: Request, db: AsyncConnection = Depends(get_db)):
    """Create a new stash."""
    # Check if stash with this name already exists
    existing_stash = await stash_repository.get_by_field(db, 'name', stash_data.name)
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

    created_stash = await stash_repository.create(db, stash)

    return {
        'stash': created_stash
    }

@router.put("/{stash_id}")
@jinja.hx('detail.html.j2')
async def update_stash(stash_id: UUID, stash_data: StashUpdate, request: Request, db: AsyncConnection = Depends(get_db)):
    """Update an existing stash."""
    # Check if stash exists
    existing_stash = await stash_repository.get_by_id(db, stash_id)
    if not existing_stash:
        raise HTTPException(status_code=404, detail="Stash not found")

    # Prepare update data
    update_data = stash_data.model_dump(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = datetime.now()

    # Update the stash
    updated_stash = await stash_repository.update(db, stash_id, update_data)

    return {
        "stash": updated_stash
    }

@router.delete("/{stash_id}")
@jinja.hx('list.html.j2')
async def delete_stash(stash_id: UUID, response: Response, db: AsyncConnection = Depends(get_db)):
    """Delete a stash."""
    # Check if stash exists
    existing_stash = await stash_repository.get_by_id(db, stash_id)
    if not existing_stash:
        raise HTTPException(status_code=404, detail="Stash not found")

    deleted = await stash_repository.delete(db, stash_id)

    response.headers['HX-Trigger'] = json.dumps({'ui.notify': 'Stash deleted successfully.' if deleted else 'Error deleting stash.'})

    return {
        "stashes": await stash_repository.get_recent(db)
    }

# Stash item endpoints
@router.post("/{stash_id}/items")
@jinja.hx('items.html.j2')
async def add_item_to_stash(stash_id: UUID, item_data: StashItemCreate, request: Request, db: AsyncConnection = Depends(get_db)):
    """Add an item to a stash."""
    # Check if stash exists
    existing_stash = await stash_repository.get_by_id(db, stash_id)
    if not existing_stash:
        raise HTTPException(status_code=404, detail="Stash not found")

    # Create the item
    item = StashItem(
        type=item_data.type,
        content=item_data.content,
        metadata=item_data.metadata
    )

    # Add the item to the stash
    updated_stash = await stash_repository.add_item(db, stash_id, item)

    return {
        "stash": updated_stash
    }

@router.delete("/{stash_id}/items/{item_index}")
@jinja.hx('items.html.j2')
async def remove_item_from_stash(stash_id: UUID, item_index: int, request: Request, db: AsyncConnection = Depends(get_db)):
    """Remove an item from a stash by its index."""
    # Check if stash exists
    existing_stash = await stash_repository.get_by_id(db, stash_id)
    if not existing_stash:
        raise HTTPException(status_code=404, detail="Stash not found")

    # Check if item index is valid
    if item_index < 0 or item_index >= len(existing_stash.items):
        raise HTTPException(status_code=400, detail="Invalid item index")

    # Remove the item from the stash
    updated_stash = await stash_repository.remove_item(db, stash_id, item_index)

    return {
        "stash": updated_stash
    }

# Entity-stash relationship endpoints
@router.post("/entity")
@jinja.hx('')
async def add_stash_to_entity(request: EntityStashRequest, db: AsyncConnection = Depends(get_db)):
    """Add a stash to an entity."""
    # Verify the stash exists
    stash = await stash_repository.get_by_id(db, request.stash_id)
    if not stash:
        raise HTTPException(status_code=404, detail="Stash not found")

    success = await entity_stash_repository.add_stash_to_entity(db, request.entity_id, request.entity_type, request.stash_id)
    if not success:
        # This might happen if the relationship already exists, depending on DB constraints
        raise HTTPException(status_code=409, detail="Relationship already exists or other database error")
    return success

@router.delete("/entity")
@jinja.hx('')
async def remove_stash_from_entity(request: EntityStashRequest, db: AsyncConnection = Depends(get_db)):
    """Remove a stash from an entity."""
    success = await entity_stash_repository.remove_stash_from_entity(db, request.entity_id, request.entity_type, request.stash_id)
    if not success:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return success

@router.get("/entity/{entity_type}/{entity_id}")
@jinja.hx('')
async def get_entity_stashes(entity_type: str, entity_id: UUID, db: AsyncConnection = Depends(get_db)):
    """Get all stashes for an entity."""
    stashes = await entity_stash_repository.get_entity_stashes(db, entity_id, entity_type)
    return stashes

# HTML component endpoints
@router.get("/components/stash-selector")
@jinja.hx('stash_selector.html.j2')
async def stash_selector_component(
    entity_id: Optional[UUID] = None,
    entity_type: Optional[str] = None,
    db: AsyncConnection = Depends(get_db)
):
    """Render a stash selector component."""
    # Get recent stashes
    stashes = await stash_repository.get_recent(db, limit=20)

    # If entity ID and type are provided, get the entity's stashes
    entity_stashes = []
    if entity_id and entity_type:
        entity_stashes = await entity_stash_repository.get_entity_stashes(db, entity_id, entity_type)

    return {
        "stashes": stashes,
        "entity_stashes": entity_stashes,
        "entity_id": entity_id,
        "entity_type": entity_type
    }

@router.get("/components/entity-stashes")
@jinja.hx('entity_stashes.html.j2')
async def entity_stashes_component(
    entity_id: UUID,
    entity_type: str,
    db: AsyncConnection = Depends(get_db)
):
    """Render the stashes for an entity."""
    stashes = await entity_stash_repository.get_entity_stashes(db, entity_id, entity_type)

    return {
        "stashes": stashes,
        "entity_id": entity_id,
        "entity_type": entity_type
    }
