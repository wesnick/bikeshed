from typing import Optional, Dict, Any
import uuid
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from src.core.workflow.engine import PersistenceProvider
from src.models.models import Session
from src.repository.session import SessionRepository
from src.service.logging import logger


class DatabasePersistenceProvider(PersistenceProvider):
    """Persistence provider that saves session state to the database"""

    def __init__(self, db_factory, session_repository=None):
        """
        Initialize the persistence provider
        
        Args:
            db_factory: Factory function that returns a database session
            session_repository: Optional repository for session operations
        """
        self.get_db = db_factory
        self.session_repo = session_repository or SessionRepository()
        self._lock = asyncio.Lock()  # Lock to prevent concurrent writes to the same session

    async def save_session(self, session: Session) -> None:
        """
        Save session state to the database
        
        Args:
            session: The session to save
        """
        async with self._lock:
            logger.info(f"Saving session {session.id} with state {session.current_state}")
            
            async for db in self.get_db():
                try:
                    # First, ensure the session exists in the database
                    db_session = await self.session_repo.get_by_id(db, session.id)
                    if not db_session:
                        # Create the session in the database
                        db.add(session)
                        await db.flush()
                    
                    # Update session data
                    await self.session_repo.update(db, session.id, {
                        'status': session.status,
                        'current_state': session.current_state,
                        'workflow_data': session.workflow_data
                    })

                    # Save any temporary messages
                    if hasattr(session, '_temp_messages') and session._temp_messages:
                        for msg in session._temp_messages:
                            # Ensure message has session_id and ID
                            if not msg.session_id:
                                msg.session_id = session.id
                            if not msg.id:
                                msg.id = uuid.uuid4()
                            db.add(msg)
                        session._temp_messages = []  # Clear the temporary messages

                    await db.commit()
                    logger.info(f"Successfully saved session {session.id}")
                except Exception as e:
                    logger.error(f"Error saving session {session.id}: {e}")
                    await db.rollback()
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
        
        async for db in self.get_db():
            try:
                # Load the session with its messages
                session = await self.session_repo.get_by_id(
                    db, 
                    session_id, 
                    load_relations=['messages']
                )
                
                if not session:
                    logger.warning(f"Session {session_id} not found")
                    return None
                
                # Initialize temporary messages list
                session._temp_messages = []
                
                logger.info(f"Successfully loaded session {session_id} with state {session.current_state}")
                return session
            except Exception as e:
                logger.error(f"Error loading session {session_id}: {e}")
                raise

    async def create_session(self, db: AsyncSession, session_data: Dict[str, Any]) -> Session:
        """
        Create a new session in the database
        
        Args:
            db: Database session
            session_data: Data for the new session
            
        Returns:
            The created session
        """
        logger.info(f"Creating new session with template {session_data.get('template', {}).get('name', 'None')}")
        
        try:
            # Create the session
            session = Session(**session_data)
            db.add(session)
            await db.flush()
            
            # Initialize temporary messages list
            session._temp_messages = []
            
            logger.info(f"Successfully created session {session.id}")
            return session
        except Exception as e:
            logger.error(f"Error creating session: {e}")
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
            'workflow_data': session.workflow_data.copy() if session.workflow_data else {},
            'messages': []
        }
        
        # Add any temporary messages
        if hasattr(session, '_temp_messages') and session._temp_messages:
            for msg in session._temp_messages:
                session_data['messages'].append({
                    'id': msg.id,
                    'role': msg.role,
                    'text': msg.text,
                    'status': msg.status
                })
            session._temp_messages = []
            
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
            workflow_data=session_data['workflow_data'].copy()
        )
        
        # Initialize temporary messages list
        session._temp_messages = []
        
        return session
        
    async def create_session(self, db: AsyncSession, session_data: Dict[str, Any]) -> Session:
        """
        Create a new session in memory
        
        Args:
            db: Database session (ignored)
            session_data: Data for the new session
            
        Returns:
            The created session
        """
        # Create a new session object
        session = Session(**session_data)
        
        # Initialize temporary messages list
        session._temp_messages = []
        
        # Save to memory
        await self.save_session(session)
        
        return session
