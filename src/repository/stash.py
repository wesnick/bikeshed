from uuid import UUID
from psycopg import AsyncConnection

from src.models.models import Stash, StashItem
from src.repository.base import BaseRepository, db_operation

class StashRepository(BaseRepository[Stash]):
    def __init__(self):
        super().__init__(Stash)
    
    @db_operation
    async def add_item(self, conn: AsyncConnection, stash_id: UUID, item: StashItem) -> Stash:
        """Add an item to a stash"""
        # First get the stash
        stash = await self.get_by_id(conn, stash_id)
        if not stash:
            raise ValueError(f"Stash with ID {stash_id} not found")
        
        # Add the new item to the items list
        stash.items.append(item)
        # Update the stash in the database - BaseRepository.update handles updated_at
        return await self.update(conn, stash_id, {"items": stash.items})

    @db_operation
    async def remove_item(self, conn: AsyncConnection, stash_id: UUID, item_index: int) -> Stash:
        """Remove an item from a stash by its index"""
        # First get the stash
        stash = await self.get_by_id(conn, stash_id)
        if not stash:
            raise ValueError(f"Stash with ID {stash_id} not found")
        
        # Check if the index is valid
        if item_index < 0 or item_index >= len(stash.items):
            raise ValueError(f"Invalid item index: {item_index}")
        
        # Remove the item
        stash.items.pop(item_index)

        # Update the stash in the database - BaseRepository.update handles updated_at
        return await self.update(conn, stash_id, {"items": stash.items})
