import json
import functools
from typing import Generic, Type, List, Optional, Any, Dict, Set
from uuid import UUID
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier
from psycopg.types.json import Jsonb

from pydantic import BaseModel

from src.models.models import DBModelMixin, T # Import the mixin and TypeVar


def db_operation(func):
    """Decorator for database operations that handles common patterns."""
    @functools.wraps(func)
    async def wrapper(self, conn: AsyncConnection, *args, **kwargs):
        try:
            result = await func(self, conn, *args, **kwargs)
            return result
        except Exception as e:
            # Optional logging
            # from src.service.logging import logger
            # logger.error(f"Error in {func.__name__}: {e}")
            raise
    return wrapper


async def prepare_data_for_db(data: Dict[str, Any], non_persisted_fields: Optional[Set[str]] = None) -> Dict[str, Any]:
    """
    Prepare data for database insertion/update.
    Serializes Pydantic models and wraps JSON-like fields in Jsonb.
    Excludes non-persisted fields and None values.
    """
    if non_persisted_fields is None:
        non_persisted_fields = set()
        
    prepared_data = {}
    
    for k, v in data.items():
        if k in non_persisted_fields or v is None:
            continue
            
        # Handle Pydantic models and collections
        if isinstance(v, BaseModel):
            prepared_data[k] = Jsonb(v.model_dump(mode='json'))
        elif isinstance(v, (list, dict)):
            # Recursively serialize any Pydantic models in collections
            serialized = json.dumps(v, default=lambda o: 
                o.model_dump(mode='json') if isinstance(o, BaseModel) else o)
            prepared_data[k] = Jsonb(json.loads(serialized))
        else:
            # Primitive type
            prepared_data[k] = v
            
    return prepared_data


async def _prepare_data_for_db(model_instance: DBModelMixin) -> Dict[str, Any]:
    """
    Prepare model data for database insertion/update.
    Excludes non-persisted fields and None values.
    """
    data = model_instance.model_dump_db()
    return await prepare_data_for_db(data, model_instance.__non_persisted_fields__)


class BaseRepository(Generic[T]):
    """Base repository for database operations using psycopg, aware of DBModelMixin."""

    def __init__(self, model: Type[T]):
        if not issubclass(model, DBModelMixin):
            raise TypeError(f"Model {model.__name__} must inherit from DBModelMixin")
        self.model = model
        self.table_name = model.__db_table__ # Use table name from mixin
        if not self.table_name:
             raise ValueError(f"Model {model.__name__} must define __db_table__")

    @db_operation
    async def get_by_id(self, conn: AsyncConnection, id: UUID) -> Optional[T]:
        """Get an entity by ID"""
        query = SQL("SELECT * FROM {} WHERE id = %s").format(Identifier(self.table_name))
        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, (id,))
            return await cur.fetchone()

    @db_operation
    async def get_all(self, conn: AsyncConnection, limit: int = 100, offset: int = 0) -> List[T]:
        """Get all entities with pagination"""
        query = SQL("SELECT * FROM {} LIMIT %s OFFSET %s").format(Identifier(self.table_name))
        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, (limit, offset))
            return await cur.fetchall()
            
    @db_operation
    async def get_recent(self, conn: AsyncConnection, limit: int = 40) -> List[T]:
        """Get the most recent entities ordered by created_at"""
        query = SQL("""
            SELECT * FROM {} 
            ORDER BY created_at DESC 
            LIMIT %s
        """).format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, (limit,))
            return await cur.fetchall()

    @db_operation
    async def get_by_field(self, conn: AsyncConnection, field: str, value: Any) -> Optional[T]:
        """Get an entity by a specific field value"""
        query = SQL("""
            SELECT * FROM {} 
            WHERE {} = %s
        """).format(Identifier(self.table_name), Identifier(field))
        
        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, (value,))
            return await cur.fetchone()

    @db_operation
    async def create(self, conn: AsyncConnection, model_instance: T) -> T:
        """Create a new entity"""
        prepared_data = await _prepare_data_for_db(model_instance)

        if not prepared_data:
            raise ValueError("No data provided for creation")

        columns = SQL(", ").join([Identifier(k) for k in prepared_data.keys()])
        placeholders = SQL(", ").join([SQL("%s") for _ in prepared_data])
        values = tuple(prepared_data.values())

        query = SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING *").format(
            Identifier(self.table_name),
            columns,
            placeholders
        )

        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, values)
            entity = await cur.fetchone()
            return entity

    @db_operation
    async def update(self, conn: AsyncConnection, id: UUID, update_data: Dict[str, Any]) -> Optional[T]:
        """
        Update an existing entity.
        Expects a dictionary of fields to update.
        Non-persisted fields in update_data will be ignored.
        The 'updated_at' field is automatically set to NOW().
        """
        # Prepare data, excluding non-persisted fields and None values
        prepared_update_data = await prepare_data_for_db(update_data)

        if not prepared_update_data:
             # If only 'updated_at' was provided or all fields were filtered out,
             # still proceed to update 'updated_at'
             if 'updated_at' in update_data:
                 pass # We will update updated_at anyway
             else:
                 # No valid fields to update, return existing record
                 return await self.get_by_id(conn, id)

        # Build SET clause and values tuple
        set_parts = []
        values_list = []
        for k, v in prepared_update_data.items():
            if isinstance(v, SQL):
                # Embed SQL functions directly (like NOW())
                set_parts.append(SQL("{} = {}").format(Identifier(k), v))
            else:
                # Use placeholders for regular values
                set_parts.append(SQL("{} = %s").format(Identifier(k)))
                values_list.append(v)

        set_clause = SQL(", ").join(set_parts)
        # Add the ID for the WHERE clause at the end of the values tuple
        values = tuple(values_list) + (id,)

        query = SQL("UPDATE {} SET {} WHERE id = %s RETURNING *").format(
            Identifier(self.table_name),
            set_clause
        )

        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, values)
            entity = await cur.fetchone()
            return entity

    @db_operation
    async def delete(self, conn: AsyncConnection, id: UUID) -> bool:
        """Delete an entity by ID"""
        query = SQL("DELETE FROM {} WHERE id = %s RETURNING id").format(Identifier(self.table_name))

        async with conn.cursor() as cur:
            await cur.execute(query, (id,))
            result = await cur.fetchone()
            success = result is not None
            return success

    async def upsert(self, conn: AsyncConnection, model_instance: T,
                     conflict_fields: List[str], update_fields: Optional[List[str]] = None) -> T:
        """
        Insert a new entity or update if it already exists based on conflict fields.

        Args:
            conn: Database connection
            model_instance: Model instance to upsert
            conflict_fields: Fields to check for conflicts (e.g., ['id', 'name'])
            update_fields: Fields to update on conflict (defaults to all fields except conflict and non-persisted fields)

        Returns:
            The created or updated entity
        """
        prepared_data = await _prepare_data_for_db(model_instance)

        if not prepared_data:
            raise ValueError("No data provided for upsert")

        # Prepare columns and values
        columns = SQL(", ").join([Identifier(k) for k in prepared_data.keys()])
        placeholders = SQL(", ").join([SQL("%s") for _ in prepared_data])
        values = tuple(prepared_data.values())

        # Prepare conflict target
        conflict_target = SQL(", ").join([Identifier(field) for field in conflict_fields])

        # Determine which fields to update on conflict
        if update_fields is None:
            # Default to all prepared fields except conflict fields and non-persisted ones (already excluded)
            update_fields = [k for k in prepared_data.keys() if k not in conflict_fields]

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
            # await conn.commit() # Commit is handled by the fixture transaction

            # If DO NOTHING was used and no row was returned, fetch the existing record
            if entity is None and not update_fields:
                # Build a query to fetch by conflict fields using prepared data
                where_clauses = SQL(" AND ").join([
                    SQL("{} = %s").format(Identifier(field))
                    for field in conflict_fields
                ])

                conflict_values = tuple(prepared_data[field] for field in conflict_fields)

                fetch_query = SQL("SELECT * FROM {} WHERE {}").format(
                    Identifier(self.table_name),
                    where_clauses
                )

                await cur.execute(fetch_query, conflict_values)
                entity = await cur.fetchone()

            return entity

    @db_operation
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


