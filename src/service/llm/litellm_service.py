import json

import litellm
from typing import Optional, Callable, Awaitable
from src.models.models import Session, Message, MessageStatus
from .base import CompletionService, LLMException


class LiteLLMCompletionService(CompletionService):
    def __init__(self, broadcast_service=None):
        self.broadcast_service = broadcast_service
        # litellm.suppress_debug_info = True
    
    def supports(self, session: Session) -> bool:
        """
        Check if this service supports the given session.
        By default, supports sessions with 'litellm' in metadata or no specific provider.
        
        Args:
            session: The session to check
            
        Returns:
            True if this service can handle the session
        """
        # If session has metadata specifying the provider
        step = session.get_current_step()
        if step and step.config_extra:
            if 'model' in step.config_extra:
                return True

        return session.template.model is not None

    async def complete(
        self,
        session: Session,
        broadcast: Optional[Callable[[Message], Awaitable[None]]] = None
    ) -> Message:
        try:
            messages = self._prepare_messages(session)
            assistant_msg = session.messages[-1]
            model = assistant_msg.model

            from src.service.logging import logger
            logger.warning(f"LiteLLM model: {json.dumps(messages, indent=4)}")

            
            # Broadcast that we're starting LLM processing
            if self.broadcast_service:
                await self.broadcast_service.broadcast("llm_update", {
                    "session_id": str(session.id),
                    "status": "processing",
                    "message_id": str(assistant_msg.id)
                })
            
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                # api_base="http://localhost:11434",  # @TODO:
                stream=True
            )
            
            content = ""
            async for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    content += delta
                    assistant_msg.text = content
                    logger.warning(f"LiteLLM messages: {content}")
                    # Use both the provided broadcast callback and our broadcast service
                    if broadcast:
                        await broadcast(assistant_msg)
                    
                    # Also broadcast via SSE if available
                    if self.broadcast_service:
                        await self.broadcast_service.broadcast("message-stream-" + str(assistant_msg.id), content)
            
            assistant_msg.text = content
            assistant_msg.status = MessageStatus.DELIVERED
            
            # Broadcast completion
            if self.broadcast_service:
                await self.broadcast_service.broadcast("llm_update", {
                    "session_id": str(session.id),
                    "status": "completed",
                    "message_id": str(assistant_msg.id)
                })
                
            return assistant_msg
            
        except Exception as e:
            assistant_msg.status = MessageStatus.FAILED
            
            # Broadcast error
            if self.broadcast_service:
                await self.broadcast_service.broadcast("llm_update", {
                    "session_id": str(session.id),
                    "status": "error",
                    "message_id": str(assistant_msg.id),
                    "error": str(e)
                })
                
            raise LLMException(f"LiteLLM error: {str(e)}") from e
