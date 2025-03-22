from uuid import UUID
from typing import List, Optional, Dict, Any
from psycopg import AsyncConnection
from psycopg.rows import class_row

from src.models.models import Session, Message
from src.repository.base import BaseRepository

class SessionRepository(BaseRepository[Session]):
    def __init__(self):
        super().__init__(Session)
        self.table_name = "session"  # Ensure correct table name

    async def get_recent_sessions(self, conn: AsyncConnection, limit: int = 40) -> List[Session]:
        """Get the most recent sessions"""
        query = """
            SELECT * FROM session 
            ORDER BY created_at DESC 
            LIMIT %s
        """
        
        async with conn.cursor(row_factory=class_row(Session)) as cur:
            await cur.execute(query, (limit,))
            return await cur.fetchall()

    async def get_with_messages(self, conn: AsyncConnection, session_id: UUID) -> Optional[Session]:
        """Get a session with all its messages"""
        # First get the session
        session_query = "SELECT * FROM session WHERE id = %s"
        
        async with conn.cursor(row_factory=class_row(Session)) as cur:
            await cur.execute(session_query, (session_id,))
            session = await cur.fetchone()
            
            if not session:
                return None
            
            # Then get all messages for this session
            messages_query = """
                SELECT * FROM message 
                WHERE session_id = %s 
                ORDER BY timestamp
            """
            
            await cur.execute(messages_query, (session_id,))
            messages = await cur.fetchall()
            
            # Manually set the messages relationship
            session.messages = messages
            
            return session
