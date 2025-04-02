from typing import Optional, Dict, Any, Callable, AsyncGenerator
import uuid
import asyncio

from psycopg import AsyncConnection

from src.core.workflow.engine import PersistenceProvider
from src.core.models import Dialog, WorkflowData
from src.components.dialog.repository import DialogRepository
from src.components.message.repository import MessageRepository
from src.service.logging import logger


class DatabasePersistenceProvider(PersistenceProvider):
    """Persistence provider that saves dialog state to the database"""

    def __init__(self, get_db: Callable[[], AsyncGenerator[AsyncConnection, None]]):
        """
        Initialize the persistence provider

        Args:
            get_db: Factory function that returns a database connection
        """
        self.get_db = get_db
        self.dialog_repo = DialogRepository()
        self.message_repo = MessageRepository()
        self._lock = asyncio.Lock()  # Lock to prevent concurrent writes to the same dialog

    async def save_dialog(self, dialog: Dialog) -> None:
        """
        Save dialog state to the database

        Args:
            dialog: The dialog to save
        """
        async with self._lock:
            logger.info(f"Saving dialog {dialog.id} with state {dialog.current_state}")

            try:
                # Acquire a connection
                async for conn in self.get_db():
                    # Save the dialog first
                    dialog_data = {
                        "status": dialog.status,
                        "current_state": dialog.current_state,
                        "workflow_data": dialog.workflow_data,
                        "error": dialog.error
                    }

                    await self.dialog_repo.update(conn, dialog.id, dialog_data)

                    # Save any messages that need to be persisted
                    for i, message in enumerate(dialog.messages):
                        # set parent lineage
                        if i > 0:
                            message.parent_id = dialog.messages[i-1].id

                        await self.message_repo.upsert(conn, message, ['id'])

                    # Commit the transaction
                    await conn.commit()
                    logger.info(f"Successfully saved dialog {dialog.id}")

            except Exception as e:
                logger.error(f"Error saving dialog {dialog.id}: {e}")
                if 'conn' in locals():
                    await conn.rollback()
                raise

    async def load_dialog(self, dialog_id: uuid.UUID) -> Optional[Dialog]:
        """
        Load dialog state from the database

        Args:
            dialog_id: ID of the dialog to load

        Returns:
            The loaded dialog or None if not found
        """
        logger.info(f"Loading dialog {dialog_id}")

        try:
            async for conn in self.get_db():
                # Load the dialog with its messages
                dialog = await self.dialog_repo.get_with_messages(conn, dialog_id)

                if not dialog:
                    logger.warning(f"Dialog {dialog_id} not found")
                    return None

                # Convert workflow_data from dict to WorkflowData if needed
                if dialog.workflow_data and isinstance(dialog.workflow_data, dict):
                    dialog.workflow_data = WorkflowData(**dialog.workflow_data)

                logger.info(f"Successfully loaded dialog {dialog_id} with state {dialog.current_state} and message count {len(dialog.messages)}")
                return dialog

        except Exception as e:
            logger.error(f"Error loading dialog {dialog_id}: {e}")
            raise

    async def create_dialog(self, dialog_data: Dict[str, Any]) -> Dialog:
        """
        Create a new dialog in the database

        Args:
            dialog_data: Data for the new dialog

        Returns:
            The created dialog
        """
        template = dialog_data.get('template')
        template_name = getattr(template, 'name', 'unknown') if template else 'unknown'
        logger.info(f"Creating new dialog with template {template_name}")

        # Create the dialog object
        dialog = Dialog(**dialog_data)

        try:
            async for conn in self.get_db():

                created_dialog = await self.dialog_repo.create(conn, dialog)

                # Commit the transaction
                await conn.commit()
                logger.info(f"Successfully created dialog {created_dialog.id}")

                return created_dialog

        except Exception as e:
            logger.error(f"Error creating dialog: {e}")
            if 'conn' in locals():
                await conn.rollback()
            raise


class InMemoryPersistenceProvider(PersistenceProvider):
    """Persistence provider that keeps dialog state in memory (for testing)"""

    def __init__(self):
        """Initialize the in-memory persistence provider"""
        self.dialogs: Dict[uuid.UUID, Dict[str, Any]] = {}

    async def save_dialog(self, dialog: Dialog) -> None:
        """
        Save dialog state to memory

        Args:
            dialog: The dialog to save
        """
        # Create a simplified representation of the dialog
        dialog_data = {
            'id': dialog.id,
            'status': dialog.status,
            'current_state': dialog.current_state,
            'workflow_data': dialog.workflow_data.model_dump() if dialog.workflow_data else {},
            'messages': []
        }

        self.dialogs[dialog.id] = dialog_data

    async def load_dialog(self, dialog_id: uuid.UUID) -> Optional[Dialog]:
        """
        Load dialog state from memory

        Args:
            dialog_id: ID of the dialog to load

        Returns:
            The loaded dialog or None if not found
        """
        if dialog_id not in self.dialogs:
            return None

        dialog_data = self.dialogs[dialog_id]

        # Create a new dialog object
        dialog = Dialog(
            id=dialog_id,
            status=dialog_data['status'],
            current_state=dialog_data['current_state'],
            workflow_data=WorkflowData(**dialog_data['workflow_data']) if dialog_data['workflow_data'] else None
        )

        return dialog

    async def create_dialog(self, dialog_data: Dict[str, Any]) -> Dialog:
        """
        Create a new dialog in memory

        Args:
            dialog_data: Data for the new dialog

        Returns:
            The created dialog
        """
        # Create a new dialog object
        dialog = Dialog(**dialog_data)

        # Save to memory
        await self.save_dialog(dialog)

        return dialog
