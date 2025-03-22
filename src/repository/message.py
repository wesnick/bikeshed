from uuid import UUID
from typing import List, Optional
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier

from src.models.models import Message
from src.repository.base import BaseRepository

class MessageRepository(BaseRepository[Message]):
    def __init__(self):
        super().__init__(Message)
        self.table_name = "messages"  # Ensure correct table name
    
    async def get_by_session(self, conn: AsyncConnection, session_id: UUID) -> List[Message]:
        """Get all messages for a session"""
        query = SQL("""
            SELECT * FROM {} 
            WHERE session_id = %s 
            ORDER BY timestamp
        """).format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Message)) as cur:
            await cur.execute(query, (session_id,))
            return await cur.fetchall()
    
    async def get_thread(self, conn: AsyncConnection, message_id: UUID) -> List[Message]:
        """Get a message and all its children (thread)"""
        # First get the root message
        root_query = SQL("SELECT * FROM {} WHERE id = %s").format(Identifier(self.table_name))
        
        async with conn.cursor(row_factory=class_row(Message)) as cur:
            await cur.execute(root_query, (message_id,))
            root_message = await cur.fetchone()
            
            if not root_message:
                return []
            
            # Then get all children
            children_query = SQL("""
                SELECT * FROM {} 
                WHERE parent_id = %s 
                ORDER BY timestamp
            """).format(Identifier(self.table_name))
            
            await cur.execute(children_query, (message_id,))
            children = await cur.fetchall()
            
            return [root_message] + children
