from typing import List, Optional
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier

from src.core.models import Tag
from src.components.base_repository import BaseRepository

class TagRepository(BaseRepository[Tag]):
    def __init__(self):
        super().__init__(Tag)
        self.table_name = "tags"  # Ensure correct table name

    async def get_by_path(self, conn: AsyncConnection, path: str) -> Optional[Tag]:
        """Get a tag by its ltree path"""
        query = SQL("SELECT * FROM {} WHERE path = %s").format(Identifier(self.table_name))

        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, (path,))
            return await cur.fetchone()

    async def get_children(self, conn: AsyncConnection, parent_path: str) -> List[Tag]:
        """Get all direct children of a path"""
        # This uses ltree's <@ operator to find direct children
        query = SQL("""
            SELECT * FROM {}
            WHERE path <@ %s AND path != %s AND nlevel(path) = nlevel(%s) + 1
            ORDER BY path
        """).format(Identifier(self.table_name))

        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, (parent_path, parent_path, parent_path))
            return await cur.fetchall()

    async def get_ancestors(self, conn: AsyncConnection, path: str) -> List[Tag]:
        """Get all ancestors of a path (excluding the path itself)"""
        # This uses ltree's @> operator to find ancestors
        query = SQL("""
            SELECT * FROM {}
            WHERE path @> %s AND path != %s
            ORDER BY path
        """).format(Identifier(self.table_name))

        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, (path, path))
            return await cur.fetchall()

    async def search_by_name(self, conn: AsyncConnection, name_pattern: str, limit: int = 20) -> List[Tag]:
        """Search tags by name using ILIKE pattern"""
        query = SQL("""
            SELECT * FROM {}
            WHERE name ILIKE %s
            ORDER BY path
            LIMIT %s
        """).format(Identifier(self.table_name))

        pattern = f"%{name_pattern}%"

        async with conn.cursor(row_factory=class_row(self.model)) as cur:
            await cur.execute(query, (pattern, limit))
            return await cur.fetchall()
