from uuid import UUID
from typing import List, Optional
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier

from src.models.models import Root
from src.repository.base import BaseRepository

class RootRepository(BaseRepository[Root]):
    def __init__(self):
        super().__init__(Root)
        self.table_name = "roots"  # Ensure correct table name
    
    async def get_with_files(self, conn: AsyncConnection, root_id: UUID) -> Optional[Root]:
        """Get a root with all its files"""
        # First get the root
        root_query = SQL("SELECT * FROM {} WHERE id = %s").format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Root)) as cur:
            await cur.execute(root_query, (root_id,))
            root = await cur.fetchone()
            
            if not root:
                return None
            
            # Then get all files for this root
            files_query = SQL("""
                SELECT * FROM root_file 
                WHERE root_id = %s 
                ORDER BY path
            """)
            
            await cur.execute(files_query, (root_id,))
            files = await cur.fetchall()
            
            # Manually set the files relationship
            root.files = files
            
            return root
    
    async def get_by_uri(self, conn: AsyncConnection, uri: str) -> Optional[Root]:
        """Get a root by its URI"""
        query = SQL("SELECT * FROM {} WHERE uri = %s").format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Root)) as cur:
            await cur.execute(query, (uri,))
            return await cur.fetchone()
    
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
            if root:
                await conn.commit()
            return root
