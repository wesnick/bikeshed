from uuid import UUID
from typing import List, Optional
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier

from src.models.models import Session, Message
from src.repository.base import BaseRepository

class SessionRepository(BaseRepository[Session]):
    def __init__(self):
        super().__init__(Session)
        self.table_name = "sessions"  # Ensure correct table name

    async def get_recent_sessions(self, conn: AsyncConnection, limit: int = 40) -> List[Session]:
        """Get the most recent sessions"""
        query = SQL("""
            SELECT * FROM {} 
            ORDER BY created_at DESC 
            LIMIT %s
        """).format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Session)) as cur:
            await cur.execute(query, (limit,))
            return await cur.fetchall()

    async def get_with_messages(self, conn: AsyncConnection, session_id: UUID) -> Optional[Session]:
        """Get a session with all its messages"""
        # First get the session
        session_query = SQL("SELECT * FROM {} WHERE id = %s").format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Session)) as cur:
            await cur.execute(session_query, (session_id,))
            session = await cur.fetchone()
            
            if not session:
                return None
            
            # Then get all messages for this session
            messages_query = SQL("""
                SELECT * FROM messages 
                WHERE session_id = %s 
                ORDER BY timestamp
            """)
            
            # Create a new cursor with the Message row factory
            async with conn.cursor(row_factory=class_row(Message)) as msg_cur:
                await msg_cur.execute(messages_query, (session_id,))
                messages = await msg_cur.fetchall()
            
            # Manually set the messages relationship
            session.messages = messages
            
            return session
