from typing import List, Dict, Any, Optional, Union, Tuple
import uuid
from datetime import datetime

from src.models.models import Session, Message
from src.core.llm import LLMMessage
from src.core.conversation.manager import MessageContext


class LLMResponseHandler:
    """
    Handles the conversion of LLM responses to database models and manages
    message persistence within sessions.
    
    Note: Most functionality has been moved to the ConversationMiddleware classes,
    but this class is maintained for backward compatibility.
    """
    
    @staticmethod
    async def create_prompt_messages(
            session: Session, 
            prompt_content: Union[str, List[Dict[str, Any]]],
            parent_id: Optional[uuid.UUID] = None
    ) -> List[Message]:
        """
        Create Message objects from prompt content
        
        Args:
            session: The session to associate messages with
            prompt_content: Either a string or a list of message parts
            parent_id: Optional parent message ID for threading
            
        Returns:
            List of created Message objects (not yet persisted to DB)
        """
        if isinstance(prompt_content, list):
            # Handle multi-part prompts
            messages = []
            current_parent_id = parent_id

            for part in prompt_content:
                msg = Message(
                    id=uuid.uuid4(),
                    session_id=session.id,
                    role=part.get("role", "user"),
                    text=part.get("content", {}).get("text", ""),
                    mime_type=part.get("content", {}).get("type", "text"),
                    status='delivered',
                    parent_id=current_parent_id
                )
                messages.append(msg)
                current_parent_id = msg.id

            return messages
        else:
            # Handle simple string prompt
            return [Message(
                id=uuid.uuid4(),
                session_id=session.id,
                role="user",
                text=prompt_content,
                status='delivered',
                parent_id=parent_id
            )]
    
    @staticmethod
    async def create_response_message(
            session: Session,
            response_text: str,
            parent_id: Optional[uuid.UUID] = None,
            model: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Create a Message object for an LLM response
        
        Args:
            session: The session to associate the message with
            response_text: The text response from the LLM
            parent_id: Optional parent message ID
            model: Optional model name that generated the response
            metadata: Optional metadata to store with the message
            
        Returns:
            Created Message object (not yet persisted to DB)
        """
        return Message(
            id=uuid.uuid4(),
            session_id=session.id,
            role="assistant",
            text=response_text,
            status='delivered',
            parent_id=parent_id,
            model=model,
            extra=metadata
        )
    
    @staticmethod
    async def process_llm_interaction(
            session: Session,
            prompt_content: Union[str, List[Dict[str, Any]]],
            response_text: str,
            parent_id: Optional[uuid.UUID] = None,
            model: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Message], Message]:
        """
        Process a complete LLM interaction (prompt and response)
        
        Args:
            session: The session to associate messages with
            prompt_content: The prompt content sent to the LLM
            response_text: The response received from the LLM
            parent_id: Optional parent message ID
            model: Optional model name
            metadata: Optional metadata
            
        Returns:
            Tuple of (prompt_messages, response_message)
        """
        # Create prompt messages
        prompt_messages = await LLMResponseHandler.create_prompt_messages(
            session, prompt_content, parent_id
        )
        
        # Create response message with parent ID from the last prompt message
        last_message_id = prompt_messages[-1].id if prompt_messages else parent_id
        response_message = await LLMResponseHandler.create_response_message(
            session, response_text, last_message_id, model, metadata
        )
        
        # Add messages to session's temporary storage
        if not hasattr(session, '_temp_messages'):
            session._temp_messages = []
        
        session._temp_messages.extend(prompt_messages + [response_message])
        
        return prompt_messages, response_message
    
    @staticmethod
    def create_from_context(context: MessageContext) -> List[Message]:
        """
        Convert context to messages using standardized mapping
        
        Args:
            context: The message context containing processed data
            
        Returns:
            List of Message objects created from the context
        """
        messages = []
        
        # Extract messages from context metadata
        if context.metadata.get("messages"):
            messages.extend(context.metadata["messages"])
        
        return messages
