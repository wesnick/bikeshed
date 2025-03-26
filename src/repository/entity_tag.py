from typing import List, Optional, Dict, Any
from uuid import UUID
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier

from src.models.models import Tag

class EntityTagRepository:
    """Repository for managing entity-tag relationships."""
    
    def __init__(self):
        self.table_name = "entity_tags"
    
    async def add_tag_to_entity(self, conn: AsyncConnection, entity_id: UUID, entity_type: str, tag_id: str) -> bool:
        """Add a tag to an entity."""
        query = SQL("""
            INSERT INTO {} (entity_id, entity_type, tag_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (entity_id, entity_type, tag_id) DO NOTHING
            RETURNING entity_id
        """).format(Identifier(self.table_name))
        
        async with conn.cursor() as cur:
            await cur.execute(query, (entity_id, entity_type, tag_id))
            result = await cur.fetchone()
            success = result is not None
            if success:
                await conn.commit()
            return success
    
    async def remove_tag_from_entity(self, conn: AsyncConnection, entity_id: UUID, entity_type: str, tag_id: str) -> bool:
        """Remove a tag from an entity."""
        query = SQL("""
            DELETE FROM {}
            WHERE entity_id = %s AND entity_type = %s AND tag_id = %s
            RETURNING entity_id
        """).format(Identifier(self.table_name))
        
        async with conn.cursor() as cur:
            await cur.execute(query, (entity_id, entity_type, tag_id))
            result = await cur.fetchone()
            success = result is not None
            if success:
                await conn.commit()
            return success
    
    async def get_entity_tags(self, conn: AsyncConnection, entity_id: UUID, entity_type: str) -> List[Tag]:
        """Get all tags for an entity."""
        query = SQL("""
            SELECT t.* FROM tags t
            JOIN {} et ON t.id = et.tag_id
            WHERE et.entity_id = %s AND et.entity_type = %s
            ORDER BY t.path
        """).format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Tag)) as cur:
            await cur.execute(query, (entity_id, entity_type))
            return await cur.fetchall()
    
    async def get_entities_with_tag(self, conn: AsyncConnection, tag_id: str, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all entities with a specific tag, optionally filtered by entity type."""
        if entity_type:
            query = SQL("""
                SELECT entity_id, entity_type FROM {}
                WHERE tag_id = %s AND entity_type = %s
            """).format(Identifier(self.table_name))
            params = (tag_id, entity_type)
        else:
            query = SQL("""
                SELECT entity_id, entity_type FROM {}
                WHERE tag_id = %s
            """).format(Identifier(self.table_name))
            params = (tag_id,)
        
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            return [{"entity_id": row[0], "entity_type": row[1]} for row in await cur.fetchall()]
    
    async def get_entities_with_any_tags(self, conn: AsyncConnection, tag_ids: List[str], entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all entities that have any of the specified tags."""
        if not tag_ids:
            return []
        
        placeholders = SQL(", ").join([SQL("%s") for _ in tag_ids])
        
        if entity_type:
            query = SQL("""
                SELECT DISTINCT entity_id, entity_type FROM {}
                WHERE tag_id IN ({}) AND entity_type = %s
            """).format(Identifier(self.table_name), placeholders)
            params = tuple(tag_ids) + (entity_type,)
        else:
            query = SQL("""
                SELECT DISTINCT entity_id, entity_type FROM {}
                WHERE tag_id IN ({})
            """).format(Identifier(self.table_name), placeholders)
            params = tuple(tag_ids)
        
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            return [{"entity_id": row[0], "entity_type": row[1]} for row in await cur.fetchall()]
    
    async def get_entities_with_all_tags(self, conn: AsyncConnection, tag_ids: List[str], entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all entities that have all of the specified tags."""
        if not tag_ids:
            return []
        
        tag_count = len(tag_ids)
        placeholders = SQL(", ").join([SQL("%s") for _ in tag_ids])
        
        if entity_type:
            query = SQL("""
                SELECT entity_id, entity_type FROM {}
                WHERE tag_id IN ({}) AND entity_type = %s
                GROUP BY entity_id, entity_type
                HAVING COUNT(DISTINCT tag_id) = %s
            """).format(Identifier(self.table_name), placeholders)
            params = tuple(tag_ids) + (entity_type, tag_count)
        else:
            query = SQL("""
                SELECT entity_id, entity_type FROM {}
                WHERE tag_id IN ({})
                GROUP BY entity_id, entity_type
                HAVING COUNT(DISTINCT tag_id) = %s
            """).format(Identifier(self.table_name), placeholders)
            params = tuple(tag_ids) + (tag_count,)
        
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            return [{"entity_id": row[0], "entity_type": row[1]} for row in await cur.fetchall()]
