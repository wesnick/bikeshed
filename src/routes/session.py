from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from fasthx import Jinja

from src.dependencies import get_db
from src.repository import session_repository, message_repository
from src.models.models import Session

router = APIRouter(prefix="/session", tags=["session"])
jinja_templates = Jinja2Templates(directory="templates")
jinja = Jinja(jinja_templates)

@router.get("/")
@jinja.hx('components/sessions.html.j2')
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """List all sessions"""
    sessions = await session_repository.get_recent_sessions(db)
    return {"sessions": sessions}

@router.get("/{session_id}")
@jinja.hx('components/session.html.j2')
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific session with its messages"""
    session = await session_repository.get_with_messages(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = await message_repository.get_by_session(db, session_id)
    return {"session": session, "messages": messages}

@router.post("/")
@jinja.hx('components/session.html.j2')
async def create_session(summary: Optional[str] = None, goal: Optional[str] = None, 
                        system_prompt: Optional[str] = None, flow_id: Optional[UUID] = None,
                        db: AsyncSession = Depends(get_db)):
    """Create a new session"""
    session_data = {
        "summary": summary,
        "goal": goal,
        "system_prompt": system_prompt,
        "flow_id": flow_id
    }
    session = await session_repository.create(db, session_data)
    return {"session": session, "messages": [], "message": "Session created successfully"}
