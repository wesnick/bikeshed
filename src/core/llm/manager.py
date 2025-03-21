from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Protocol
from pydantic import BaseModel

from src.models import Session
from src.core.llm.llm import LLMMessage

@dataclass
class MessageContext:
    """Standardized conversation context"""
    session: Session
    model: str
    raw_input: Optional[Any] = None
    processed_input: Optional[List[Dict]] = None
    llm_messages: Optional[List[LLMMessage]] = None
    output: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=list)
    retry: int = 0
    """Number of retries so far."""


class ConversationMiddleware(Protocol):
    """Protocol for conversation middleware components"""
    async def handle(self, context: MessageContext, next_fn: Callable) -> MessageContext:
        """
        Process the message context and call the next middleware
        
        Args:
            context: The current message context
            next_fn: Function to call the next middleware
            
        Returns:
            Updated message context
        """
        ...

class ConversationManager:
    """
    Manages the conversation processing pipeline using middleware components
    """
    
    def __init__(self, middlewares: List[ConversationMiddleware]):
        """
        Initialize the conversation manager
        
        Args:
            middlewares: List of middleware components to use in the pipeline
        """
        self.middlewares = middlewares
        
    async def process(self, context: MessageContext) -> MessageContext:
        """
        Process a message context through the middleware chain
        
        Args:
            context: The initial message context
            
        Returns:
            The processed message context
        """
        async def next_handler(current_middleware_index: int) -> MessageContext:
            if current_middleware_index < len(self.middlewares):
                return await self.middlewares[current_middleware_index].handle(
                    context, 
                    lambda: next_handler(current_middleware_index + 1)
                )
            return context
            
        return await next_handler(0)
