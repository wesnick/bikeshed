from abc import ABC, abstractmethod
from typing import Optional, Callable, Awaitable, List
from src.models.models import Session, Message

class LLMException(Exception):
    """Base exception for LLM service errors"""
    pass

class CompletionService(ABC):
    @abstractmethod
    async def complete(
        self,
        session: Session,
        broadcast: Optional[Callable[[Message], Awaitable[None]]] = None
    ) -> Message:
        """
        Process a conversation session and generate a completion.
        
        Args:
            session: The session with conversation history
            broadcast: Optional callback for streaming updates
            
        Returns:
            The assistant Message with completion
        """
        pass
    
    @abstractmethod
    def supports(self, session: Session) -> bool:
        """
        Determine if this completion service supports the given session.
        
        Args:
            session: The session to check
            
        Returns:
            True if this service can handle the session, False otherwise
        """
        pass

    def _prepare_messages(self, session: Session) -> list[dict]:
        """Convert session messages to LLM message format"""
        return [{
            "role": msg.role,
            "content": msg.text
        } for msg in session.messages[:-1]]  # Exclude last message (assistant stub)

class ChainedCompletionService(CompletionService):
    """
    A completion service that chains multiple services together and uses the first one that supports the session.
    """
    
    def __init__(self, services: List[CompletionService]):
        """
        Initialize with a list of completion services to try in order.
        
        Args:
            services: List of CompletionService implementations to try
        """
        self.services = services
    
    def supports(self, session: Session) -> bool:
        """Always returns True as long as there's at least one service"""
        return len(self.services) > 0
    
    async def complete(
        self,
        session: Session,
        broadcast: Optional[Callable[[Message], Awaitable[None]]] = None
    ) -> Message:
        """
        Find the first service that supports the session and use it to complete.
        
        Args:
            session: The session with conversation history
            broadcast: Optional callback for streaming updates
            
        Returns:
            The assistant Message with completion
            
        Raises:
            LLMException: If no service supports the session
        """
        for service in self.services:
            if service.supports(session):
                return await service.complete(session, broadcast)
        
        raise LLMException("No completion service supports this session")
