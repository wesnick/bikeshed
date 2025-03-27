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
            
            # Create a new cursor with the RootFile row factory for fetching files
            async with conn.cursor(row_factory=class_row(RootFile)) as files_cur:
                await files_cur.execute(files_query, (root_id,))
                files = await files_cur.fetchall()
            
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
        """Get the most recently created roots"""
        query = SQL("""
            SELECT * FROM {} 
            ORDER BY created_at DESC 
            LIMIT %s
        """).format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Root)) as cur:
            await cur.execute(query, (limit,))
            return await cur.fetchall()
