from uuid import UUID
from typing import List, Optional
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier

from src.models.models import Stash, StashItem
from src.repository.base import BaseRepository

class StashRepository(BaseRepository[Stash]):
    def __init__(self):
        super().__init__(Stash)
        self.table_name = "stashes"  # Ensure correct table name

    async def get_recent_stashes(self, conn: AsyncConnection, limit: int = 40) -> List[Stash]:
        """Get the most recent stashes"""
        query = SQL("""
            SELECT * FROM {} 
            ORDER BY created_at DESC 
            LIMIT %s
        """).format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Stash)) as cur:
            await cur.execute(query, (limit,))
            return await cur.fetchall()
    
    async def get_by_name(self, conn: AsyncConnection, name: str) -> Optional[Stash]:
        """Get a stash by its name"""
        query = SQL("""
            SELECT * FROM {} 
            WHERE name = %s
        """).format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Stash)) as cur:
            await cur.execute(query, (name,))
            return await cur.fetchone()
    
    async def add_item(self, conn: AsyncConnection, stash_id: UUID, item: StashItem) -> Stash:
        """Add an item to a stash"""
        # First get the stash
        stash = await self.get_by_id(conn, stash_id)
        if not stash:
            raise ValueError(f"Stash with ID {stash_id} not found")
        
        # Add the new item to the items list
        stash.items.append(item)
        
        # Update the stash in the database
        return await self.update(conn, stash_id, {"items": stash.items, "updated_at": stash.updated_at})
    
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
        
        # Update the stash in the database
        return await self.update(conn, stash_id, {"items": stash.items, "updated_at": stash.updated_at})
