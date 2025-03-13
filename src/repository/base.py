from typing import Generic, TypeVar, Type, List, Optional, Any, Dict, Union
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from src.models.models import Base

T = TypeVar('T', bound=Base)

class BaseRepository(Generic[T]):
    """Base repository for database operations"""
    
    def __init__(self, model: Type[T]):
        self.model = model
    
    async def get_by_id(self, db: AsyncSession, id: UUID, load_relations: List[str] = None) -> Optional[T]:
        """Get an entity by ID with optional relation loading"""
        query = select(self.model).where(self.model.id == id)
        
        if load_relations:
            for relation in load_relations:
                query = query.options(selectinload(getattr(self.model, relation)))
                
        result = await db.execute(query)
        return result.scalars().first()
    
    async def get_all(self, db: AsyncSession, limit: int = 100, offset: int = 0, 
                     load_relations: List[str] = None) -> List[T]:
        """Get all entities with pagination and optional relation loading"""
        query = select(self.model).limit(limit).offset(offset)
        
        if load_relations:
            for relation in load_relations:
                query = query.options(selectinload(getattr(self.model, relation)))
                
        result = await db.execute(query)
        return result.scalars().all()
    
    async def create(self, db: AsyncSession, data: Dict[str, Any]) -> T:
        """Create a new entity"""
        entity = self.model(**data)
        db.add(entity)
        await db.commit()
        await db.refresh(entity)
        return entity
    
    async def update(self, db: AsyncSession, id: UUID, data: Dict[str, Any]) -> Optional[T]:
        """Update an existing entity"""
        entity = await self.get_by_id(db, id)
        if not entity:
            return None
            
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
                
        await db.commit()
        await db.refresh(entity)
        return entity
    
    async def delete(self, db: AsyncSession, id: UUID) -> bool:
        """Delete an entity by ID"""
        entity = await self.get_by_id(db, id)
        if not entity:
            return False
            
        await db.delete(entity)
        await db.commit()
        return True
    
    async def filter(self, db: AsyncSession, filters: Dict[str, Any], 
                    limit: int = 100, offset: int = 0,
                    load_relations: List[str] = None) -> List[T]:
        """Filter entities by attributes"""
        query = select(self.model)
        
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
        
        query = query.limit(limit).offset(offset)
        
        if load_relations:
            for relation in load_relations:
                query = query.options(selectinload(getattr(self.model, relation)))
                
        result = await db.execute(query)
        return result.scalars().all()
