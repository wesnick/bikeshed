from typing import Callable, List, Dict, Any, Optional
import uuid
from datetime import datetime

from src.core.conversation.manager import MessageContext, ConversationMiddleware
from src.core.llm import LLMService, LLMMessageFactory, LLMMessage
from src.models import Message, Session
from src.service.logging import logger

class MessagePersistenceMiddleware(ConversationMiddleware):
    """Middleware for persisting messages to the database"""
    
    async def handle(self, context: MessageContext, next_fn: Callable) -> MessageContext:
        """
        Handle message persistence before and after processing
        
        Args:
            context: The current message context
            next_fn: Function to call the next middleware
            
        Returns:
            Updated message context
        """
        # Pre-processing: Save incoming messages
        if context.raw_input:
            # Create user message
            user_message = Message(
                id=uuid.uuid4(),
                session_id=context.session.id,
                role="user",
                text=context.raw_input if isinstance(context.raw_input, str) else str(context.raw_input),
                status='delivered',
                parent_id=context.metadata.get("parent_id"),
                model=context.metadata.get("model"),
                extra=context.metadata.get("extra")
            )
            
            # Add to session's temporary storage
            if not hasattr(context.session, '_temp_messages'):
                context.session._temp_messages = []
            
            context.session._temp_messages.append(user_message)
            
            # Update context with the created message
            if not context.metadata.get("messages"):
                context.metadata["messages"] = []
            context.metadata["messages"].append(user_message)
            
        # Continue processing
        updated_context = await next_fn()
        
        # Post-processing: Save response if available
        if updated_context.output:
            # Create assistant message
            parent_id = None
            if updated_context.metadata.get("messages") and len(updated_context.metadata["messages"]) > 0:
                parent_id = updated_context.metadata["messages"][-1].id
            
            response_message = Message(
                id=uuid.uuid4(),
                session_id=context.session.id,
                role="assistant",
                text=updated_context.output if isinstance(updated_context.output, str) else str(updated_context.output),
                status='delivered',
                parent_id=parent_id,
                model=context.metadata.get("model"),
                extra=context.metadata.get("extra")
            )
            
            # Add to session's temporary storage
            if not hasattr(context.session, '_temp_messages'):
                context.session._temp_messages = []
            
            context.session._temp_messages.append(response_message)
            
            # Update context with the created message
            if not updated_context.metadata.get("messages"):
                updated_context.metadata["messages"] = []
            updated_context.metadata["messages"].append(response_message)
        
        return updated_context

class LLMProcessingMiddleware(ConversationMiddleware):
    """Middleware for processing messages with an LLM service"""
    
    def __init__(self, llm_service: LLMService):
        """
        Initialize the LLM processing middleware
        
        Args:
            llm_service: Service for LLM interactions
        """
        self.llm_service = llm_service
        
    async def handle(self, context: MessageContext, next_fn: Callable) -> MessageContext:
        """
        Process the message context with an LLM service
        
        Args:
            context: The current message context
            next_fn: Function to call the next middleware
            
        Returns:
            Updated message context
        """
        # Convert to LLM format if not already done
        if not context.llm_messages:
            # Get existing messages from the session
            existing_messages = []
            if hasattr(context.session, '_temp_messages'):
                existing_messages = context.session._temp_messages
            
            # Convert to LLM messages
            context.llm_messages = LLMMessageFactory.from_session_messages(
                context.session, 
                existing_messages
            )
            
        # Generate response from LLM
        logger.info(f"Generating LLM response with {len(context.llm_messages)} messages")
        response = await self.llm_service.generate_response(context.llm_messages)
        context.output = response
        
        # Continue processing
        return await next_fn()

class TemplateProcessingMiddleware(ConversationMiddleware):
    """Middleware for processing prompt templates"""
    
    def __init__(self, registry):
        """
        Initialize the template processing middleware
        
        Args:
            registry: Registry for prompt templates
        """
        self.registry = registry
        
    async def handle(self, context: MessageContext, next_fn: Callable) -> MessageContext:
        """
        Process prompt templates in the message context
        
        Args:
            context: The current message context
            next_fn: Function to call the next middleware
            
        Returns:
            Updated message context
        """
        # Check if we have a template to process
        step = context.metadata.get("step")
        if step and step.get("template"):
            # Get variables and template args
            variables = context.session.workflow_data.get('variables', {})
            template_args = step.get("template_args") or {}

            # Combine variables and template args
            args = {**variables, **template_args}

            # Get prompt from registry
            prompt = self.registry.get_prompt(step.get("template"))
            if prompt:
                # Render the prompt
                rendered_prompt = await prompt.render(args)
                context.raw_input = rendered_prompt
        
        # Continue processing
        return await next_fn()

class SessionUpdateMiddleware(ConversationMiddleware):
    """Middleware for updating session state"""
    
    async def handle(self, context: MessageContext, next_fn: Callable) -> MessageContext:
        """
        Update session state before and after processing
        
        Args:
            context: The current message context
            next_fn: Function to call the next middleware
            
        Returns:
            Updated message context
        """
        # Pre-processing: Update session status
        context.session.status = 'running'
        context.session.last_activity = datetime.now()
        
        # Continue processing
        updated_context = await next_fn()
        
        # Post-processing: Update session status
        if updated_context.output:
            context.session.status = 'completed'
        else:
            context.session.status = 'waiting_for_input'
        
        return updated_context
