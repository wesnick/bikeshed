import asyncio
from faker import Faker
from typing import Optional, Callable, Awaitable
from src.models.models import Session, Message, MessageStatus
from .base import CompletionService

class FakerLLMConfig:
    def __init__(self, response_delay: float = 0.2, fake_stream: bool = True):
        self.response_delay = response_delay
        self.fake_stream = fake_stream

class FakerCompletionService(CompletionService):
    def __init__(self, config: FakerLLMConfig = None, broadcast_service=None):
        self.faker = Faker()
        self.config = config or FakerLLMConfig()
        self.broadcast_service = broadcast_service
    
    def supports(self, session: Session) -> bool:
        """
        Check if this service supports the given session.
        Supports sessions with 'faker' as model or test sessions.
        
        Args:
            session: The session to check
            
        Returns:
            True if this service can handle the session
        """
        # Check the last message for the model, then the session for the model
        if session.messages and session.messages[-1].model:
            return session.messages[-1].model == 'faker'

        if session.template and session.template.model:
            return session.template.model == 'faker'

        return False

    async def complete(
        self,
        session: Session,
        broadcast: Optional[Callable[[Message], Awaitable[None]]] = None
    ) -> Message:
        assistant_msg = session.messages[-1]
        
        # Broadcast that we're starting LLM processing
        if self.broadcast_service:
            await self.broadcast_service.broadcast("llm_update", {
                "session_id": str(session.id),
                "status": "processing",
                "message_id": str(assistant_msg.id)
            })
        
        if self.config.fake_stream:
            for i in range(50):
                await asyncio.sleep(self.config.response_delay)
                assistant_msg.text = assistant_msg.text + f" {self.faker.bs()}"
                
                # Use both the provided broadcast callback and our broadcast service
                if broadcast:
                    await broadcast(assistant_msg)
                
                # Also broadcast via SSE if available
                if self.broadcast_service:
                    await self.broadcast_service.broadcast("message-stream-" + str(assistant_msg.id), assistant_msg.text)
        else:
            await asyncio.sleep(self.config.response_delay)
            assistant_msg.text = self.faker.paragraph(nb_sentences=10)
            
            if broadcast:
                await broadcast(assistant_msg)
                
            if self.broadcast_service:
                await self.broadcast_service.broadcast("message_update", {
                    "session_id": str(session.id),
                    "message_id": str(assistant_msg.id),
                    "content": assistant_msg.text,
                    "status": "complete"
                })
        
        assistant_msg.status = MessageStatus.DELIVERED
        
        # Broadcast completion
        if self.broadcast_service:
            await self.broadcast_service.broadcast("llm_update", {
                "session_id": str(session.id),
                "status": "completed",
                "message_id": str(assistant_msg.id)
            })
            
        return assistant_msg
