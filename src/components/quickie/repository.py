from uuid import UUID
from typing import List, Optional, Dict, Any
from psycopg import AsyncConnection
from psycopg.rows import class_row

from src.core.models import Quickie, QuickieStatus
from src.components.base_repository import BaseRepository, db_operation

class QuickieRepository(BaseRepository[Quickie]):
    """Repository for managing Quickie objects"""

    def __init__(self):
        super().__init__(Quickie)

    @db_operation
    async def get_by_template_name(self, conn: AsyncConnection, template_name: str, limit: int = 100) -> List[Quickie]:
        """Get quickies by template name"""
        query = """
            SELECT * FROM quickies
            WHERE template_name = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        async with conn.cursor(row_factory=class_row(Quickie)) as cur:
            await cur.execute(query, (template_name, limit))
            return await cur.fetchall()

    @db_operation
    async def get_by_prompt_hash(self, conn: AsyncConnection, prompt_hash: str) -> Optional[Quickie]:
        """Get a quickie by its prompt hash"""
        return await self.get_by_field(conn, "prompt_hash", prompt_hash)

    @db_operation
    async def update_status(self, conn: AsyncConnection, quickie_id: UUID,
                           status: QuickieStatus, error: Optional[str] = None) -> Quickie:
        """Update the status of a quickie"""
        update_data = {"status": status}
        if error is not None:
            update_data["error"] = error
        return await self.update(conn, quickie_id, update_data)

    @db_operation
    async def update_output(self, conn: AsyncConnection, quickie_id: UUID,
                           output: Any, metadata: Optional[Dict[str, Any]] = None) -> Quickie:
        """Update the output of a quickie"""
        update_data = {
            "output": output,
            "status": QuickieStatus.COMPLETE
        }
        if metadata is not None:
            update_data["metadata"] = metadata
        return await self.update(conn, quickie_id, update_data)

    @db_operation
    async def get_recent_by_status(self, conn: AsyncConnection, status: QuickieStatus,
                                  limit: int = 20) -> List[Quickie]:
        """Get recent quickies by status"""
        query = """
            SELECT * FROM quickies
            WHERE status = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        async with conn.cursor(row_factory=class_row(Quickie)) as cur:
            await cur.execute(query, (status.value, limit))
            return await cur.fetchall()
