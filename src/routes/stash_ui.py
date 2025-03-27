from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from psycopg import AsyncConnection

from src.models.models import Stash, StashItem
from src.dependencies import get_db, get_jinja
from src.service.stash_service import StashService

router = APIRouter(prefix="/stashes", tags=["stashes-ui"])
stash_service = StashService()
jinja = get_jinja()

@router.get("")
@jinja.hx('components/stash/list.html.j2')
async def list_stashes(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncConnection = Depends(get_db)
):
    """List all stashes."""
    stashes = await stash_service.get_recent_stashes(db, limit)
    return {"stashes": stashes}

@router.get("/{stash_id}")
@jinja.hx('components/stash/detail.html.j2')
async def get_stash_detail(stash_id: UUID, db: AsyncConnection = Depends(get_db)):
    """Get a stash by ID."""
    stash = await stash_service.get_stash(db, stash_id)
    if not stash:
        raise HTTPException(status_code=404, detail="Stash not found")
    return {"stash": stash}

@router.get("/create")
@jinja.hx('components/stash/create.html.j2')
async def create_stash_form():
    """Render the create stash form."""
    return {}

@router.get("/{stash_id}/edit")
@jinja.hx('components/stash/edit.html.j2')
async def edit_stash_form(stash_id: UUID, db: AsyncConnection = Depends(get_db)):
    """Render the edit stash form."""
    stash = await stash_service.get_stash(db, stash_id)
    if not stash:
        raise HTTPException(status_code=404, detail="Stash not found")
    return {"stash": stash}

@router.get("/{stash_id}/items")
@jinja.hx('components/stash/items.html.j2')
async def get_stash_items(stash_id: UUID, db: AsyncConnection = Depends(get_db)):
    """Get items for a stash."""
    stash = await stash_service.get_stash(db, stash_id)
    if not stash:
        raise HTTPException(status_code=404, detail="Stash not found")
    return {"stash": stash}

@router.get("/{stash_id}/add-item")
@jinja.hx('components/stash/add_item.html.j2')
async def add_item_form(stash_id: UUID, db: AsyncConnection = Depends(get_db)):
    """Render the add item form."""
    stash = await stash_service.get_stash(db, stash_id)
    if not stash:
        raise HTTPException(status_code=404, detail="Stash not found")
    return {"stash": stash}
