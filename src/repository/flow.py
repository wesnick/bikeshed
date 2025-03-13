from uuid import UUID
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from src.models.models import Flow
from src.repository.base import BaseRepository

class FlowRepository(BaseRepository[Flow]):
    def __init__(self):
        super().__init__(Flow)
    
    async def get_recent_flows(self, db: AsyncSession, limit: int = 10) -> List[Flow]:
        """Get the most recent flows"""
        query = select(Flow).order_by(desc(Flow.created_at)).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_by_name(self, db: AsyncSession, name: str) -> Optional[Flow]:
        """Get a flow by name"""
        query = select(Flow).where(Flow.name == name)
        result = await db.execute(query)
        return result.scalars().first()
