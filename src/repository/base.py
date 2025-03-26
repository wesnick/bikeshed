import json
from typing import Generic, Type, List, Optional, Any, Dict, Set
from uuid import UUID
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier
from psycopg.types.json import Jsonb

from pydantic import BaseModel

from src.models.models import DBModelMixin, T # Import the mixin and TypeVar


def _pydantic_serializer(obj):
    """Custom JSON serializer for Pydantic models and other types."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode='json')
    # Add other type handlers if needed (e.g., datetime)
    # Let psycopg handle standard types
    return obj


async def _prepare_data_for_db(model_instance: DBModelMixin) -> Dict[str, Any]:
    """
    Prepare model data for database insertion/update.
    Excludes non-persisted fields and None values. Relies on global psycopg
    JSON serializer for complex types.
    """
    data = model_instance.model_dump_db()
    prepared_data = {}

    for k, v in data.items():
        if isinstance(v, list):
            # Check if list items are models or dicts, requiring Jsonb wrapping for the whole list
            if v and (isinstance(v[0], BaseModel) or isinstance(v[0], dict)):
                 prepared_data[k] = Jsonb(v) # Wrap the entire list
            else:
                 prepared_data[k] = v # Assume list of primitives
        elif isinstance(v, BaseModel) or isinstance(v, dict):
            prepared_data[k] = Jsonb(v) # Wrap individual model/dict
        else:
            prepared_data[k] = v # Handle other types

    return prepared_data


class BaseRepository(Generic[T]):
    """Base repository for database operations using psycopg, aware of DBModelMixin."""

    def __init__(self, model: Type[T]):
        if not issubclass(model, DBModelMixin):
            raise TypeError(f"Model {model.__name__} must inherit from DBModelMixin")
        self.model = model
        self.table_name = model.__db_table__ # Use table name from mixin
        if not self.table_name:
             raise ValueError(f"Model {model.__name__} must define __db_table__")

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

        from src.service.logging import logger
        logger.warning(f"Values: {values}")

        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, values)
            entity = await cur.fetchone()
            # await conn.commit() # Removed: Handled by db_conn_clean fixture transaction
            return entity

    async def update(self, conn: AsyncConnection, id: UUID, update_data: Dict[str, Any]) -> Optional[T]:
        """
        Update an existing entity.
        Expects a dictionary of fields to update.
        Non-persisted fields in update_data will be ignored.
        """
        # Filter out non-persisted fields and None values from the input dict
        valid_update_data = {}
        for k, v in update_data.items():
             if k not in self.model.__non_persisted_fields__ and v is not None:
                 # Check if the field type annotation suggests JSON/dict/list or if it's a Pydantic model/dict
                 field_info = self.model.model_fields.get(k)
                 is_json_like = False
                 # Check if the value itself requires Jsonb wrapping
                 if isinstance(v, dict) or (isinstance(v, list) and v and (isinstance(v[0], BaseModel) or isinstance(v[0], dict))):
                     valid_update_data[k] = Jsonb(v)
                 else:
                     valid_update_data[k] = v # Assume primitive or let psycopg handle it

            # Check if 'id' was the only thing passed, which isn't an update
            if 'id' in update_data and len(update_data) == 1:
                 return await self.get_by_id(conn, id)
            # Otherwise, maybe only non-persisted fields were passed, raise or log?
            # For now, let's proceed, maybe only updated_at needs changing.
            pass # Or return await self.get_by_id(conn, id) if no update is truly intended

        # Always update the updated_at timestamp
        valid_update_data['updated_at'] = SQL("NOW()") # Use SQL function

        # Adjust values tuple creation for SQL("NOW()") and build SET clause
        values_list = []
        final_set_parts = []
        for k, v in valid_update_data.items():
            if isinstance(v, SQL):
                 # If the value is already SQL (like NOW()), embed it directly
                 final_set_parts.append(SQL("{} = {}").format(Identifier(k), v))
            else:
                 # Otherwise, use a placeholder and add the value to the list
                 final_set_parts.append(SQL("{} = %s").format(Identifier(k)))
                 values_list.append(v)

        final_set_clause = SQL(", ").join(final_set_parts)
        values = tuple(values_list) + (id,) # Add the ID for the WHERE clause


        query = SQL("UPDATE {} SET {} WHERE id = %s RETURNING *").format(
            Identifier(self.table_name),
            final_set_clause
        )

        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, values)
            entity = await cur.fetchone()
            # if entity: # Commit is handled by the fixture transaction
            #     await conn.commit()
            return entity

    async def delete(self, conn: AsyncConnection, id: UUID) -> bool:
        """Delete an entity by ID"""
        query = SQL("DELETE FROM {} WHERE id = %s RETURNING id").format(Identifier(self.table_name))

        async with conn.cursor() as cur:
            await cur.execute(query, (id,))
            result = await cur.fetchone()
            success = result is not None
            # if success: # Commit is handled by the fixture transaction
            #     await conn.commit()
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


