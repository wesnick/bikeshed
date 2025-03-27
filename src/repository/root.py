from uuid import UUID
from typing import List, Optional
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier
from psycopg.types.json import Jsonb

from src.models.models import Root, RootFile
from src.repository.base import BaseRepository, db_operation

class RootRepository(BaseRepository[Root]):
    def __init__(self):
        super().__init__(Root)
        self.table_name = "roots"  # Ensure correct table name
    
    @db_operation
    async def get_with_files(self, conn: AsyncConnection, root_id: UUID) -> Optional[Root]:
        """Get a root with all its files"""
        # First get the root
        root_query = SQL("SELECT * FROM {} WHERE id = %s").format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Root)) as cur:
            await cur.execute(root_query, (root_id,))
            root = await cur.fetchone()
            
            if not root:
                return None
            
            # Then get all files for this root - use correct table name "root_files"
            files_query = SQL("""
                SELECT * FROM root_files 
                WHERE root_id = %s 
                ORDER BY path
            """)
            
            await cur.execute(files_query, (root_id,))
            files = await cur.fetchall()
            
            # Manually set the files relationship
            root.files = files
            
            return root
    
    @db_operation
    async def get_by_uri(self, conn: AsyncConnection, uri: str) -> Optional[Root]:
        """Get a root by its URI"""
        query = SQL("SELECT * FROM {} WHERE uri = %s").format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Root)) as cur:
            await cur.execute(query, (uri,))
            return await cur.fetchone()
    
    @db_operation
    async def get_recent_roots(self, conn: AsyncConnection, limit: int = 10) -> List[Root]:
        """Get the most recently accessed roots"""
        query = SQL("""
            SELECT * FROM {} 
            ORDER BY last_accessed_at DESC 
            LIMIT %s
        """).format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Root)) as cur:
            await cur.execute(query, (limit,))
            return await cur.fetchall()
    
    @db_operation
    async def update_last_accessed(self, conn: AsyncConnection, root_id: UUID) -> Optional[Root]:
        """Update the last_accessed_at timestamp for a root"""
        query = SQL("""
            UPDATE {} 
            SET last_accessed_at = NOW() 
            WHERE id = %s 
            RETURNING *
        """).format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Root)) as cur:
            await cur.execute(query, (root_id,))
            root = await cur.fetchone()
            # Remove the explicit commit as it's handled by the db_operation decorator
            return root
