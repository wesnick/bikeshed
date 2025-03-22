import litellm
from typing import Optional, Callable, Awaitable
from src.models.models import Session, Message, MessageStatus
from .base import CompletionService, LLMException

class LiteLLMConfig:
    def __init__(self, provider: str, model: str, api_key: str):
        self.provider = provider
        self.model = model
        self.api_key = api_key

class LiteLLMCompletionService(CompletionService):
    def __init__(self, config: LiteLLMConfig):
        self.config = config
        litellm.suppress_debug_info = True

    async def complete(
        self,
        session: Session,
        broadcast: Optional[Callable[[Message], Awaitable[None]]] = None
    ) -> Message:
        try:
            messages = self._prepare_messages(session)
            assistant_msg = session.messages[-1]
            
            response = await litellm.acompletion(
                model=f"{self.config.provider}/{self.config.model}",
                messages=messages,
                api_key=self.config.api_key,
                stream=True
            )
            
            content = ""
            async for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    content += delta
                    assistant_msg.text = content
                    if broadcast:
                        await broadcast(assistant_msg)
            
            assistant_msg.text = content
            assistant_msg.status = MessageStatus.DELIVERED
            return assistant_msg
            
        except Exception as e:
            assistant_msg.status = MessageStatus.FAILED
            raise LLMException(f"LiteLLM error: {str(e)}") from e
