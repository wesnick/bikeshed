from typing import Optional, Dict, Any, Callable, AsyncGenerator
import uuid
import asyncio

from psycopg import AsyncConnection

from src.core.workflow.engine import PersistenceProvider
from src.models.models import Session, SessionStatus, WorkflowData
from src.repository.session import SessionRepository
from src.repository.message import MessageRepository
from src.service.logging import logger


class DatabasePersistenceProvider(PersistenceProvider):
    """Persistence provider that saves session state to the database"""

    def __init__(self, get_db: Callable[[], AsyncGenerator[AsyncConnection, None]]):
        """
        Initialize the persistence provider
        
        Args:
            get_db: Factory function that returns a database connection
        """
        self.get_db = get_db
        self.session_repo = SessionRepository()
        self.message_repo = MessageRepository()
        self._lock = asyncio.Lock()  # Lock to prevent concurrent writes to the same session

    async def save_session(self, session: Session) -> None:
        """
        Save session state to the database
        
        Args:
            session: The session to save
        """
        async with self._lock:
            logger.info(f"Saving session {session.id} with state {session.current_state}")

            try:
                # Acquire a connection
                async for conn in self.get_db():
                    # Save the session first
                    session_data = {
                        "status": session.status,
                        "current_state": session.current_state,
                        "workflow_data": session.workflow_data,
                        "error": session.error
                    }

                    await self.session_repo.update(conn, session.id, session_data)

                    # Save any messages that need to be persisted
                    for i, message in enumerate(session.messages):
                        # set parent lineage
                        if i > 0:
                            message.parent_id = session.messages[i-1].id

                        await self.message_repo.upsert(conn, message, ['id'])

                    # Commit the transaction
                    await conn.commit()
                    logger.info(f"Successfully saved session {session.id}")

            except Exception as e:
                logger.error(f"Error saving session {session.id}: {e}")
                if 'conn' in locals():
                    await conn.rollback()
                raise

    async def load_session(self, session_id: uuid.UUID) -> Optional[Session]:
        """
        Load session state from the database
        
        Args:
            session_id: ID of the session to load
            
        Returns:
            The loaded session or None if not found
        """
        logger.info(f"Loading session {session_id}")

        try:
            async for conn in self.get_db():
                # Load the session with its messages
                session = await self.session_repo.get_with_messages(conn, session_id)
                
                if not session:
                    logger.warning(f"Session {session_id} not found")
                    return None

                # Convert workflow_data from dict to WorkflowData if needed
                if session.workflow_data and isinstance(session.workflow_data, dict):
                    session.workflow_data = WorkflowData(**session.workflow_data)
                
                logger.info(f"Successfully loaded session {session_id} with state {session.current_state} and message count {len(session.messages)}")
                return session
                
        except Exception as e:
            logger.error(f"Error loading session {session_id}: {e}")
            raise

    async def create_session(self, session_data: Dict[str, Any]) -> Session:
        """
        Create a new session in the database
        
        Args:
            session_data: Data for the new session
            
        Returns:
            The created session
        """
        template = session_data.get('template')
        template_name = getattr(template, 'name', 'unknown') if template else 'unknown'
        logger.info(f"Creating new session with template {template_name}")
        
        # Create the session object
        session = Session(**session_data)

        try:
            async for conn in self.get_db():

                created_session = await self.session_repo.create(conn, session)

                # Commit the transaction
                await conn.commit()
                logger.info(f"Successfully created session {created_session.id}")

                return created_session

        except Exception as e:
            logger.error(f"Error creating session: {e}")
            if 'conn' in locals():
                await conn.rollback()
            raise


class InMemoryPersistenceProvider(PersistenceProvider):
    """Persistence provider that keeps session state in memory (for testing)"""
    
    def __init__(self):
        """Initialize the in-memory persistence provider"""
        self.sessions: Dict[uuid.UUID, Dict[str, Any]] = {}
        
    async def save_session(self, session: Session) -> None:
        """
        Save session state to memory
        
        Args:
            session: The session to save
        """
        # Create a simplified representation of the session
        session_data = {
            'id': session.id,
            'status': session.status,
            'current_state': session.current_state,
            'workflow_data': session.workflow_data.model_dump() if session.workflow_data else {},
            'messages': []
        }

        self.sessions[session.id] = session_data
        
    async def load_session(self, session_id: uuid.UUID) -> Optional[Session]:
        """
        Load session state from memory
        
        Args:
            session_id: ID of the session to load
            
        Returns:
            The loaded session or None if not found
        """
        if session_id not in self.sessions:
            return None
            
        session_data = self.sessions[session_id]
        
        # Create a new session object
        session = Session(
            id=session_id,
            status=session_data['status'],
            current_state=session_data['current_state'],
            workflow_data=WorkflowData(**session_data['workflow_data']) if session_data['workflow_data'] else None
        )

        return session
        
    async def create_session(self, session_data: Dict[str, Any]) -> Session:
        """
        Create a new session in memory
        
        Args:
            session_data: Data for the new session
            
        Returns:
            The created session
        """
        # Create a new session object
        session = Session(**session_data)

        # Save to memory
        await self.save_session(session)
        
        return session
