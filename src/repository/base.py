from typing import Generic, TypeVar, Type, List, Optional, Any, Dict, Union, cast
from uuid import UUID
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier, Composed, Literal
from psycopg.types.json import Jsonb

from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


async def filter_data(data: Dict[str, Any], exclude_fields: list = None) -> Dict[str, Any]:
    filtered_data = {k: v for k, v in data.items() if v is not None and (exclude_fields is None or k not in exclude_fields)}

    # Process the values - wrap Pydantic models with Jsonb
    processed_values = {}
    for k, v in filtered_data.items():
        if isinstance(v, BaseModel) or isinstance(v, dict):
            # Option 1: If you set a global dumps function
            processed_values[k] = Jsonb(v)

        else:
            processed_values[k] = v

    return processed_values


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

    async def create(self, conn: AsyncConnection, model: BaseModel) -> T:
        """Create a new entity"""
        # Filter out None values to allow default values to be used
        data = model.model_dump()
        filtered_data = await filter_data(data, model.__non_persisted_fields__)

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
        filtered_data = await filter_data(data)

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
            
    async def upsert(self, conn: AsyncConnection, model: BaseModel, 
                     conflict_fields: List[str], update_fields: Optional[List[str]] = None) -> T:
        """
        Insert a new entity or update if it already exists based on conflict fields.
        
        Args:
            conn: Database connection
            model: Model instance to upsert
            conflict_fields: Fields to check for conflicts (e.g., ['id', 'name'])
            update_fields: Fields to update on conflict (defaults to all fields except conflict fields)
            
        Returns:
            The created or updated entity
        """
        data = model.model_dump()
        filtered_data = await filter_data(data, model.__non_persisted_fields__)
        
        if not filtered_data:
            raise ValueError("No data provided for upsert")
            
        # Prepare columns and values
        columns = SQL(", ").join([Identifier(k) for k in filtered_data.keys()])
        placeholders = SQL(", ").join([SQL("%s") for _ in filtered_data])
        values = tuple(filtered_data.values())
        
        # Prepare conflict target
        conflict_target = SQL(", ").join([Identifier(field) for field in conflict_fields])
        
        # Determine which fields to update on conflict
        if update_fields is None:
            # Default to all fields except conflict fields
            update_fields = [k for k in filtered_data.keys() if k not in conflict_fields]
        
        # Prepare update clause
        if update_fields:
            set_clause = SQL(", ").join([
                SQL("{} = EXCLUDED.{}").format(Identifier(field), Identifier(field)) 
                for field in update_fields
            ])
            
            query = SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET {} RETURNING *").format(
                Identifier(self.table_name),
                columns,
                placeholders,
                conflict_target,
                set_clause
            )
        else:
            # If no fields to update, do nothing on conflict
            query = SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO NOTHING RETURNING *").format(
                Identifier(self.table_name),
                columns,
                placeholders,
                conflict_target
            )
        
        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, values)
            entity = await cur.fetchone()
            await conn.commit()
            
            # If DO NOTHING was used and no row was returned, fetch the existing record
            if entity is None and not update_fields:
                # Build a query to fetch by conflict fields
                where_clauses = SQL(" AND ").join([
                    SQL("{} = %s").format(Identifier(field)) 
                    for field in conflict_fields
                ])
                conflict_values = tuple(filtered_data[field] for field in conflict_fields)
                
                fetch_query = SQL("SELECT * FROM {} WHERE {}").format(
                    Identifier(self.table_name),
                    where_clauses
                )
                
                await cur.execute(fetch_query, conflict_values)
                entity = await cur.fetchone()
                
            return entity

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


