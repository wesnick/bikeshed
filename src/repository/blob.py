from typing import List, Optional, Dict, Any
from uuid import UUID

from psycopg.rows import class_row
from psycopg_pool import AsyncConnection

from src.models.models import Blob
from src.repository.base import BaseRepository


class BlobRepository(BaseRepository[Blob]):
    def __init__(self):
        super().__init__(Blob)
    
    async def get_by_content_hash(self, conn: AsyncConnection, sha256: str) -> Optional[Blob]:
        """Get a blob by its SHA-256 hash"""
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE sha256 = %s
        """
        row = await conn.execute(query, (sha256,), fetch_one=True)
        if not row:
            return None
        return self.model_class.model_validate(dict(row))
    
    async def search(
        self, 
        conn: AsyncConnection, 
        query: str, 
        limit: int = 20, 
        offset: int = 0
    ) -> List[Blob]:
        """Search for blobs by name or description"""
        search_query = f"""
            SELECT * FROM {self.table_name}
            WHERE name ILIKE %s OR description ILIKE %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        search_term = f"%{query}%"
        rows = await conn.execute(
            search_query, 
            (search_term, search_term, limit, offset),
            fetch_all=True
        )
        return [self.model_class.model_validate(dict(row)) for row in rows]
