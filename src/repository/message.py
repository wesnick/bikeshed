from uuid import UUID
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from src.models.models import Message
from src.repository.base import BaseRepository

class MessageRepository(BaseRepository[Message]):
    def __init__(self):
        super().__init__(Message)
    
    async def get_by_session(self, db: AsyncSession, session_id: UUID) -> List[Message]:
        """Get all messages for a session"""
        query = select(Message).where(Message.session_id == session_id).order_by(Message.timestamp)
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_thread(self, db: AsyncSession, message_id: UUID) -> List[Message]:
        """Get a message and all its children (thread)"""
        # First get the message
        query = select(Message).where(Message.id == message_id)
        result = await db.execute(query)
        root_message = result.scalars().first()
        
        if not root_message:
            return []
            
        # Then get all children
        query = select(Message).where(Message.parent_id == message_id).order_by(Message.timestamp)
        result = await db.execute(query)
        children = result.scalars().all()
        
        return [root_message] + children
