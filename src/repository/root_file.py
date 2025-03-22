from uuid import UUID
from typing import List, Optional, Dict, Any
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier

from src.models.models import RootFile
from src.repository.base import BaseRepository

class RootFileRepository(BaseRepository[RootFile]):
    def __init__(self):
        super().__init__(RootFile)
        self.table_name = "root_files"  # Ensure correct table name
    
    async def get_by_path(self, conn: AsyncConnection, root_id: UUID, path: str) -> Optional[RootFile]:
        """Get a file by its path within a root"""
        query = SQL("""
            SELECT * FROM {} 
            WHERE root_id = %s AND path = %s
        """).format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(RootFile)) as cur:
            await cur.execute(query, (root_id, path))
            return await cur.fetchone()
    
    async def get_files_by_root(self, conn: AsyncConnection, root_id: UUID) -> List[RootFile]:
        """Get all files for a root"""
        query = SQL("""
            SELECT * FROM {} 
            WHERE root_id = %s 
            ORDER BY path
        """).format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(RootFile)) as cur:
            await cur.execute(query, (root_id,))
            return await cur.fetchall()
    
    async def get_files_by_extension(self, conn: AsyncConnection, root_id: UUID, extension: str) -> List[RootFile]:
        """Get all files with a specific extension in a root"""
        query = SQL("""
            SELECT * FROM {} 
            WHERE root_id = %s AND extension = %s
            ORDER BY path
        """).format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(RootFile)) as cur:
            await cur.execute(query, (root_id, extension))
            return await cur.fetchall()
    
    async def search_files(self, conn: AsyncConnection, root_id: UUID, search_term: str) -> List[RootFile]:
        """Search for files by name or path"""
        query = SQL("""
            SELECT * FROM {} 
            WHERE root_id = %s AND (
                name ILIKE %s OR
                path ILIKE %s
            )
            ORDER BY path
        """).format(Identifier(self.table_name))
        
        search_pattern = f"%{search_term}%"
        
        async with conn.cursor(row_factory=class_row(RootFile)) as cur:
            await cur.execute(query, (root_id, search_pattern, search_pattern))
            return await cur.fetchall()
    
    async def bulk_create(self, conn: AsyncConnection, files: List[Dict[str, Any]]) -> List[RootFile]:
        """Create multiple files at once"""
        if not files:
            return []
        
        # Ensure all files have the same structure
        first_file = files[0]
        columns = list(first_file.keys())
        
        # Build the query
        columns_sql = SQL(", ").join([Identifier(col) for col in columns])
        
        # Create a VALUES clause for each file
        values_template = SQL(", ").join([SQL("%s") for _ in columns])
        all_values_sql = SQL(", ").join(
            [SQL("({})").format(values_template) for _ in files]
        )
        
        # Flatten the values list
        values = []
        for file_data in files:
            for col in columns:
                values.append(file_data.get(col))
        
        query = SQL("""
            INSERT INTO {} ({}) 
            VALUES {} 
            RETURNING *
        """).format(
            Identifier(self.table_name),
            columns_sql,
            all_values_sql
        )
        
        async with conn.cursor(row_factory=class_row(RootFile)) as cur:
            await cur.execute(query, values)
            created_files = await cur.fetchall()
            await conn.commit()
            return created_files
