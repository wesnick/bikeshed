from typing import List, Dict, Any, Optional
from uuid import UUID
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier

from src.models.models import Stash

class EntityStashRepository:
    """Repository for managing entity-stash relationships."""
    
    def __init__(self):
        self.table_name = "entity_stashes"
    
    async def add_stash_to_entity(self, conn: AsyncConnection, entity_id: UUID, entity_type: str, stash_id: UUID) -> bool:
        """Add a stash to an entity."""
        query = SQL("""
            INSERT INTO {} (entity_id, entity_type, stash_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (entity_id, entity_type, stash_id) DO NOTHING
            RETURNING entity_id
        """).format(Identifier(self.table_name))
        
        async with conn.cursor() as cur:
            await cur.execute(query, (entity_id, entity_type, stash_id))
            result = await cur.fetchone()
            success = result is not None
            if success:
                await conn.commit()
            return success
    
    async def remove_stash_from_entity(self, conn: AsyncConnection, entity_id: UUID, entity_type: str, stash_id: UUID) -> bool:
        """Remove a stash from an entity."""
        query = SQL("""
            DELETE FROM {}
            WHERE entity_id = %s AND entity_type = %s AND stash_id = %s
            RETURNING entity_id
        """).format(Identifier(self.table_name))
        
        async with conn.cursor() as cur:
            await cur.execute(query, (entity_id, entity_type, stash_id))
            result = await cur.fetchone()
            success = result is not None
            if success:
                await conn.commit()
            return success
    
    async def get_entity_stashes(self, conn: AsyncConnection, entity_id: UUID, entity_type: str) -> List[Stash]:
        """Get all stashes for an entity."""
        query = SQL("""
            SELECT s.* FROM stashes s
            JOIN {} es ON s.id = es.stash_id
            WHERE es.entity_id = %s AND es.entity_type = %s
            ORDER BY s.created_at DESC
        """).format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Stash)) as cur:
            await cur.execute(query, (entity_id, entity_type))
            return await cur.fetchall()
    
    async def get_entities_with_stash(self, conn: AsyncConnection, stash_id: UUID, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all entities with a specific stash, optionally filtered by entity type."""
        if entity_type:
            query = SQL("""
                SELECT entity_id, entity_type FROM {}
                WHERE stash_id = %s AND entity_type = %s
            """).format(Identifier(self.table_name))
            params = (stash_id, entity_type)
        else:
            query = SQL("""
                SELECT entity_id, entity_type FROM {}
                WHERE stash_id = %s
            """).format(Identifier(self.table_name))
            params = (stash_id,)
        
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            return [{"entity_id": row[0], "entity_type": row[1]} for row in await cur.fetchall()]
