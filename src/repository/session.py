from uuid import UUID
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from src.models.models import Session
from src.repository.base import BaseRepository

class SessionRepository(BaseRepository[Session]):
    def __init__(self):
        super().__init__(Session)
    
    async def get_recent_sessions(self, db: AsyncSession, limit: int = 40) -> List[Session]:
        """Get the most recent sessions"""
        query = select(Session).order_by(desc(Session.created_at)).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_sessions_by_flow(self, db: AsyncSession, flow_id: UUID) -> List[Session]:
        """Get all sessions for a specific flow"""
        query = select(Session).where(Session.flow_id == flow_id).order_by(desc(Session.created_at))
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_with_messages(self, db: AsyncSession, session_id: UUID) -> Optional[Session]:
        """Get a session with all its messages"""
        query = select(Session).where(Session.id == session_id).options(
            selectinload(Session.messages)
        )
        result = await db.execute(query)
        return result.scalars().first()
