from uuid import UUID
from typing import List, Optional, Dict, Any
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier

from src.models.models import RootFile, T
from src.repository.base import BaseRepository, db_operation

class RootFileRepository(BaseRepository[RootFile]):
    def __init__(self):
        super().__init__(RootFile)
        self.table_name = "root_files"
        self.pk_columns = ["root_uri", "path"] # Composite primary key

    @db_operation
    async def get_by_pk(self, conn: AsyncConnection, root_uri: str, path: str) -> Optional[RootFile]:
        """Get a file by its composite primary key (root_uri, path)"""
        query = SQL("""
            SELECT * FROM {}
            WHERE root_uri = %s AND path = %s
        """).format(Identifier(self.table_name))

        async with conn.cursor(row_factory=class_row(RootFile)) as cur:
            await cur.execute(query, (root_uri, path))
            return await cur.fetchone()

    @db_operation
    async def get_files_by_root(self, conn: AsyncConnection, root_uri: str) -> List[RootFile]:
        """Get all files for a root"""
        query = SQL("""
            SELECT * FROM {}
            WHERE root_uri = %s
            ORDER BY path
        """).format(Identifier(self.table_name))

        async with conn.cursor(row_factory=class_row(RootFile)) as cur:
            await cur.execute(query, (root_uri,))
            return await cur.fetchall()

    @db_operation
    async def get_files_by_extension(self, conn: AsyncConnection, root_uri: str, extension: str) -> List[RootFile]:
        """Get all files with a specific extension in a root"""
        query = SQL("""
            SELECT * FROM {}
            WHERE root_uri = %s AND extension = %s
            ORDER BY path
        """).format(Identifier(self.table_name))

        async with conn.cursor(row_factory=class_row(RootFile)) as cur:
            await cur.execute(query, (root_uri, extension))
            return await cur.fetchall()

    @db_operation
    async def search_files(self, conn: AsyncConnection, root_uri: str, search_term: str) -> List[RootFile]:
        """Search for files by name or path within a specific root"""
        query = SQL("""
            SELECT * FROM {}
            WHERE root_uri = %s AND (
                name ILIKE %s OR
                path ILIKE %s
            )
            ORDER BY path
        """).format(Identifier(self.table_name))

        search_pattern = f"%{search_term}%"

        async with conn.cursor(row_factory=class_row(RootFile)) as cur:
            await cur.execute(query, (root_uri, search_pattern, search_pattern))
            return await cur.fetchall()

    # Note: BaseRepository's create, update, delete might need adjustments
    # if they assume a single 'id' primary key. Overriding them or modifying
    # BaseRepository might be necessary. bulk_create below is custom.

    @db_operation
    async def bulk_create(self, conn: AsyncConnection, files: List[RootFile]) -> List[RootFile]:
        """Create multiple RootFile instances at once."""
        if not files:
            return []
        # Prepare data, excluding non-persisted fields
        file_data_list = [f.model_dump_db() for f in files]
        if not file_data_list:
            return []

        first_file_data = file_data_list[0]
        columns = list(first_file_data.keys())
        columns_sql = SQL(", ").join(map(Identifier, columns))

        # Create placeholders for each file's values
        values_placeholders = SQL(", ").join([SQL("%s")] * len(columns))
        all_values_sql = SQL(", ").join([SQL("({})").format(values_placeholders)] * len(file_data_list))

        # Flatten the list of values
        flat_values = [file_data[col] for file_data in file_data_list for col in columns]

        query = SQL("""
            INSERT INTO {} ({})
            VALUES {}
            ON CONFLICT (root_uri, path) DO UPDATE SET
                name = EXCLUDED.name,
                extension = EXCLUDED.extension,
                mime_type = EXCLUDED.mime_type,
                size = EXCLUDED.size,
                atime = EXCLUDED.atime,
                mtime = EXCLUDED.mtime,
                ctime = EXCLUDED.ctime,
                extra = EXCLUDED.extra
            RETURNING *
        """).format(
            Identifier(self.table_name), columns_sql, all_values_sql
        )

        async with conn.cursor(row_factory=class_row(RootFile)) as cur:
            await cur.execute(query, flat_values)
            # Fetchall might return results for both inserts and updates
            results = await cur.fetchall()
            # Commit is handled by the db_operation decorator
            return results

    @db_operation
    async def delete(self, conn: AsyncConnection, root_uri: str, path: str) -> bool:
        query = SQL("DELETE FROM {} WHERE root_uri = %s AND path = %s").format(Identifier(self.table_name))
        async with conn.cursor() as cur:
            await cur.execute(query, (root_uri, path))
            return cur.rowcount > 0

    async def get_by_id(self, conn: AsyncConnection, id: UUID | str) -> Optional[T]:
        raise NotImplemented

    @db_operation
    async def update(self, conn: AsyncConnection, root_uri: str, path: str, data: Dict[str, Any]) -> Optional[RootFile]:
        raise NotImplemented
