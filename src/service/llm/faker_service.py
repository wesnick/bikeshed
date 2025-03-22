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
    def __init__(self, config: FakerLLMConfig = None):
        self.faker = Faker()
        self.config = config or FakerLLMConfig()

    async def complete(
        self,
        session: Session,
        broadcast: Optional[Callable[[Message], Awaitable[None]]] = None
    ) -> Message:
        assistant_msg = session.messages[-1]
        response = self.faker.paragraph(nb_sentences=5)
        
        if self.config.fake_stream:
            words = response.split()
            for i in range(len(words)):
                await asyncio.sleep(self.config.response_delay)
                assistant_msg.text = " ".join(words[:i+1])
                if broadcast:
                    await broadcast(assistant_msg)
        else:
            await asyncio.sleep(self.config.response_delay)
            assistant_msg.text = response
            if broadcast:
                await broadcast(assistant_msg)
        
        assistant_msg.status = MessageStatus.DELIVERED
        return assistant_msg
