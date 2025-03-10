from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
import uuid
from src.models import Message

class MessageRepository:
    """Repository for managing Message entities"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, message_data: Dict[str, Any]) -> Message:
        """Create a new message"""
        message = Message.create_from_dict(message_data)
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message
    
    async def get_by_id(self, message_id: uuid.UUID) -> Optional[Message]:
        """Get a message by ID"""
        result = await self.session.execute(
            select(Message).where(Message.id == message_id)
        )
        return result.scalars().first()
    
    async def get_all(self, limit: int = 100) -> List[Message]:
        """Get all messages, ordered by creation date (newest first)"""
        result = await self.session.execute(
            select(Message)
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_thread(self, message_id: uuid.UUID) -> List[Message]:
        """Get a thread of messages starting from the given message ID"""
        # First get the message
        message = await self.get_by_id(message_id)
        if not message:
            return []
        
        # Get all ancestors (parent chain)
        ancestors = []
        current_id = message.parent_id
        while current_id:
            parent = await self.get_by_id(current_id)
            if not parent:
                break
            ancestors.insert(0, parent)  # Insert at beginning to maintain order
            current_id = parent.parent_id
        
        # Get all descendants (children recursively)
        descendants = await self._get_descendants(message_id)
        
        # Combine all messages in the thread
        return ancestors + [message] + descendants
    
    async def _get_descendants(self, message_id: uuid.UUID) -> List[Message]:
        """Recursively get all descendants of a message"""
        result = await self.session.execute(
            select(Message).where(Message.parent_id == message_id)
        )
        children = result.scalars().all()
        
        descendants = list(children)
        for child in children:
            child_descendants = await self._get_descendants(child.id)
            descendants.extend(child_descendants)
        
        return descendants
    
    async def update(self, message_id: uuid.UUID, message_data: Dict[str, Any]) -> Optional[Message]:
        """Update a message"""
        message = await self.get_by_id(message_id)
        if not message:
            return None
        
        # Update fields
        for key, value in message_data.items():
            if hasattr(message, key):
                setattr(message, key, value)
        
        await self.session.commit()
        await self.session.refresh(message)
        return message
    
    async def delete(self, message_id: uuid.UUID) -> bool:
        """Delete a message"""
        message = await self.get_by_id(message_id)
        if not message:
            return False
        
        await self.session.delete(message)
        await self.session.commit()
        return True
