from typing import Generic, TypeVar, Type, List, Optional, Any, Dict, Union, cast
from uuid import UUID
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier, Composed, Literal

from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class BaseRepository(Generic[T]):
    """Base repository for database operations using psycopg"""
    
    def __init__(self, model: Type[T]):
        self.model = model
        self.table_name = model.__name__.lower()
    
    async def get_by_id(self, conn: AsyncConnection, id: UUID) -> Optional[T]:
        """Get an entity by ID"""
        query = SQL("SELECT * FROM {} WHERE id = %s").format(Identifier(self.table_name))
        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, (id,))
            return await cur.fetchone()
    
    async def get_all(self, conn: AsyncConnection, limit: int = 100, offset: int = 0) -> List[T]:
        """Get all entities with pagination"""
        query = SQL("SELECT * FROM {} LIMIT %s OFFSET %s").format(Identifier(self.table_name))
        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, (limit, offset))
            return await cur.fetchall()
    
    async def create(self, conn: AsyncConnection, data: Dict[str, Any]) -> T:
        """Create a new entity"""
        # Filter out None values to allow default values to be used
        filtered_data = {k: v for k, v in data.items() if v is not None}
        
        if not filtered_data:
            raise ValueError("No data provided for creation")
        
        columns = SQL(", ").join([Identifier(k) for k in filtered_data.keys()])
        placeholders = SQL(", ").join([SQL("%s") for _ in filtered_data])
        values = tuple(filtered_data.values())
        
        query = SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING *").format(
            Identifier(self.table_name),
            columns,
            placeholders
        )
        
        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, values)
            entity = await cur.fetchone()
            await conn.commit()
            return entity
    
    async def update(self, conn: AsyncConnection, id: UUID, data: Dict[str, Any]) -> Optional[T]:
        """Update an existing entity"""
        # Filter out None values
        filtered_data = {k: v for k, v in data.items() if v is not None}
        
        if not filtered_data:
            return await self.get_by_id(conn, id)
        
        set_clause = SQL(", ").join([SQL("{} = %s").format(Identifier(k)) for k in filtered_data.keys()])
        values = tuple(filtered_data.values()) + (id,)
        
        query = SQL("UPDATE {} SET {} WHERE id = %s RETURNING *").format(
            Identifier(self.table_name),
            set_clause
        )
        
        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, values)
            entity = await cur.fetchone()
            if entity:
                await conn.commit()
            return entity
    
    async def delete(self, conn: AsyncConnection, id: UUID) -> bool:
        """Delete an entity by ID"""
        query = SQL("DELETE FROM {} WHERE id = %s RETURNING id").format(Identifier(self.table_name))
        
        async with conn.cursor() as cur:
            await cur.execute(query, (id,))
            result = await cur.fetchone()
            success = result is not None
            if success:
                await conn.commit()
            return success
    
    async def filter(self, conn: AsyncConnection, filters: Dict[str, Any], 
                    limit: int = 100, offset: int = 0) -> List[T]:
        """Filter entities by attributes"""
        if not filters:
            return await self.get_all(conn, limit, offset)
        
        where_clauses = SQL(" AND ").join([SQL("{} = %s").format(Identifier(k)) for k in filters.keys()])
        values = tuple(filters.values()) + (limit, offset)
        
        query = SQL("SELECT * FROM {} WHERE {} LIMIT %s OFFSET %s").format(
            Identifier(self.table_name),
            where_clauses
        )
        
        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, values)
            return await cur.fetchall()
