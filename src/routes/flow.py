from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from fasthx import Jinja

from src.dependencies import get_db
from src.repository import flow_repository
from src.models.models import Flow

router = APIRouter(prefix="/flow", tags=["flow"])
jinja_templates = Jinja2Templates(directory="templates")
jinja = Jinja(jinja_templates)

@router.get("/")
@jinja.hx('components/flows.html.j2')
async def list_flows(db: AsyncSession = Depends(get_db)):
    """List all flows"""
    flows = await flow_repository.get_recent_flows(db)
    return {"flows": flows}

@router.get("/{flow_id}")
@jinja.hx('components/flow_detail.html.j2')
async def get_flow(flow_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific flow"""
    flow = await flow_repository.get_by_id(db, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return {"flow": flow}

@router.post("/")
@jinja.hx('components/flow_detail.html.j2')
async def create_flow(name: str, description: Optional[str] = None, 
                     goal: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Create a new flow"""
    flow_data = {
        "name": name,
        "description": description,
        "goal": goal,
        "current_state": "initial"
    }
    flow = await flow_repository.create(db, flow_data)
    return {"flow": flow, "message": "Flow created successfully"}
