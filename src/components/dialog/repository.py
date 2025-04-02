from uuid import UUID
from typing import List, Optional
from psycopg import AsyncConnection
from psycopg.rows import class_row
from psycopg.sql import SQL, Identifier

from src.core.models import Dialog, Message
from src.components.base_repository import BaseRepository

class DialogRepository(BaseRepository[Dialog]):
    def __init__(self):
        super().__init__(Dialog)
        self.table_name = "dialogs"  # Ensure correct table name

    async def get_recent_dialogs(self, conn: AsyncConnection, limit: int = 40) -> List[Dialog]:
        """Get the most recent dialogs"""
        query = SQL("""
            SELECT * FROM {}
            ORDER BY created_at DESC
            LIMIT %s
        """).format(Identifier(self.table_name))

        async with conn.cursor(row_factory=class_row(Dialog)) as cur:
            await cur.execute(query, (limit,))
            return await cur.fetchall()

    async def get_active_dialogs(self, conn: AsyncConnection) -> List[Dialog]:
        """Get all active dialogs (running or waiting for input)"""
        query = SQL("""
            SELECT * FROM {}
            WHERE status IN ('running', 'waiting_for_input')
            ORDER BY created_at DESC
        """).format(Identifier(self.table_name))

        async with conn.cursor(row_factory=class_row(Dialog)) as cur:
            await cur.execute(query)
            return await cur.fetchall()

    async def get_with_messages(self, conn: AsyncConnection, dialog_id: UUID) -> Optional[Dialog]:
        """Get a dialog with all its messages"""
        # First get the dialog
        dialog_query = SQL("SELECT * FROM {} WHERE id = %s").format(Identifier(self.table_name))

        async with conn.cursor(row_factory=class_row(Dialog)) as cur:
            await cur.execute(dialog_query, (dialog_id,))
            dialog = await cur.fetchone()

            if not dialog:
                return None

            # Then get all messages for this dialog
            messages_query = SQL("""
                SELECT * FROM messages
                WHERE dialog_id = %s
                ORDER BY timestamp
            """)

            # Create a new cursor with the Message row factory
            async with conn.cursor(row_factory=class_row(Message)) as msg_cur:
                await msg_cur.execute(messages_query, (dialog_id,))
                messages = await msg_cur.fetchall()

            # Manually set the messages relationship
            dialog.messages = messages

            return dialog
