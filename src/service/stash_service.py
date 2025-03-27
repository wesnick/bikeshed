from typing import List, Optional, Dict, Any
from uuid import UUID
from psycopg import AsyncConnection

from src.models.models import Stash, StashItem
from src.repository.stash import StashRepository
from src.repository.entity_stash import EntityStashRepository

class StashService:
    """Service for managing stashes and entity-stash relationships."""
    
    def __init__(self):
        self.stash_repo = StashRepository()
        self.entity_stash_repo = EntityStashRepository()
    
    async def get_stash(self, conn: AsyncConnection, stash_id: UUID) -> Optional[Stash]:
        """Get a stash by ID."""
        return await self.stash_repo.get_by_id(conn, stash_id)
    
    async def get_stash_by_name(self, conn: AsyncConnection, name: str) -> Optional[Stash]:
        """Get a stash by name."""
        return await self.stash_repo.get_by_field(conn, 'name', name)
    
    async def create_stash(self, conn: AsyncConnection, stash: Stash) -> Stash:
        """Create a new stash."""
        return await self.stash_repo.create(conn, stash)
    
    async def update_stash(self, conn: AsyncConnection, stash_id: UUID, update_data: Dict[str, Any]) -> Optional[Stash]:
        """Update an existing stash."""
        return await self.stash_repo.update(conn, stash_id, update_data)
    
    async def delete_stash(self, conn: AsyncConnection, stash_id: UUID) -> bool:
        """Delete a stash."""
        return await self.stash_repo.delete(conn, stash_id)
    
    async def get_recent_stashes(self, conn: AsyncConnection, limit: int = 40) -> List[Stash]:
        """Get the most recent stashes."""
        return await self.stash_repo.get_recent(conn, limit)
    
    async def add_item_to_stash(self, conn: AsyncConnection, stash_id: UUID, item: StashItem) -> Stash:
        """Add an item to a stash."""
        return await self.stash_repo.add_item(conn, stash_id, item)
    
    async def remove_item_from_stash(self, conn: AsyncConnection, stash_id: UUID, item_index: int) -> Stash:
        """Remove an item from a stash by its index."""
        return await self.stash_repo.remove_item(conn, stash_id, item_index)
    
    # Entity-stash relationship methods
    
    async def add_stash_to_entity(self, conn: AsyncConnection, entity_id: UUID, entity_type: str, stash_id: UUID) -> bool:
        """Add a stash to an entity."""
        # Verify the stash exists
        stash = await self.stash_repo.get_by_id(conn, stash_id)
        if not stash:
            return False
        
        return await self.entity_stash_repo.add_stash_to_entity(conn, entity_id, entity_type, stash_id)
    
    async def remove_stash_from_entity(self, conn: AsyncConnection, entity_id: UUID, entity_type: str, stash_id: UUID) -> bool:
        """Remove a stash from an entity."""
        return await self.entity_stash_repo.remove_stash_from_entity(conn, entity_id, entity_type, stash_id)
    
    async def get_entity_stashes(self, conn: AsyncConnection, entity_id: UUID, entity_type: str) -> List[Stash]:
        """Get all stashes for an entity."""
        return await self.entity_stash_repo.get_entity_stashes(conn, entity_id, entity_type)
    
    async def get_entities_with_stash(self, conn: AsyncConnection, stash_id: UUID, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all entities with a specific stash."""
        return await self.entity_stash_repo.get_entities_with_stash(conn, stash_id, entity_type)
