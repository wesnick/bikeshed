import asyncio
from faker import Faker
from typing import Optional, Callable, Awaitable
from src.models.models import Session, Message, MessageStatus
from .base import CompletionService

class FakerLLMConfig:
    def __init__(self, response_delay: float = 0.5, fake_stream: bool = True):
        self.response_delay = response_delay
        self.fake_stream = fake_stream

class FakerCompletionService(CompletionService):
    def __init__(self, config: FakerLLMConfig = None, broadcast_service=None):
        self.faker = Faker()
        self.config = config or FakerLLMConfig()
        self.broadcast_service = broadcast_service

    async def complete(
        self,
        session: Session,
        broadcast: Optional[Callable[[Message], Awaitable[None]]] = None
    ) -> Message:
        assistant_msg = session.messages[-1]
        response = self.faker.paragraph(nb_sentences=5)
        
        # Broadcast that we're starting LLM processing
        if self.broadcast_service:
            await self.broadcast_service.broadcast("llm_update", {
                "session_id": str(session.id),
                "status": "processing",
                "message_id": str(assistant_msg.id)
            })
        
        if self.config.fake_stream:
            words = response.split()
            for i in range(len(words)):
                await asyncio.sleep(self.config.response_delay)
                assistant_msg.text = " ".join(words[:i+1])
                
                # Use both the provided broadcast callback and our broadcast service
                if broadcast:
                    await broadcast(assistant_msg)
                
                # Also broadcast via SSE if available
                if self.broadcast_service:
                    await self.broadcast_service.broadcast("message_update", {
                        "session_id": str(session.id),
                        "message_id": str(assistant_msg.id),
                        "content": assistant_msg.text,
                        "status": "streaming"
                    })
        else:
            await asyncio.sleep(self.config.response_delay)
            assistant_msg.text = response
            
            if broadcast:
                await broadcast(assistant_msg)
                
            if self.broadcast_service:
                await self.broadcast_service.broadcast("message_update", {
                    "session_id": str(session.id),
                    "message_id": str(assistant_msg.id),
                    "content": response,
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
