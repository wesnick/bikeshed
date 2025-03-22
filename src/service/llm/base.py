from abc import ABC, abstractmethod
from typing import Optional, Callable, Awaitable
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

    def _prepare_messages(self, session: Session) -> list[dict]:
        """Convert session messages to LLM message format"""
        return [{
            "role": msg.role,
            "content": msg.text
        } for msg in session.messages[:-1]]  # Exclude last message (assistant stub)
