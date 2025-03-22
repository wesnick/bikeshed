import uuid
from typing import Dict, Any, Optional, Callable, Awaitable

from src.core.config_types import PromptStep, Step
from src.core.registry import Registry
from src.models import Message
from src.models.models import Session, SessionStatus, MessageStatus
from src.core.workflow.engine import StepHandler
from src.service.llm import CompletionService


class PromptStepHandler(StepHandler):
    """Handler for prompt steps"""

    def __init__(self, registry: Registry, llm_service: CompletionService):
        """
        Initialize the PromptStepHandler
        
        Args:
            registry: Registry instance
            llm_service: Optional CompletionService instance
        """
        self.registry = registry
        self.llm_service = llm_service

    async def can_handle(self, session: Session, step: Step) -> bool:
        """Check if the step can be handled"""
        if not isinstance(step, PromptStep):
            return False

        # If no template, no variables needed
        if not step.template:
            return True

        # Check all required variables
        variables = session.workflow_data.variables
        template_args = step.template_args or {}

        # Get prompt from registry
        prompt = self.registry.get_prompt(step.template)

        if not prompt:
            raise ValueError(f"Prompt template '{step.template}' not found")

        # Get required variables not in template_args
        required_vars = [arg.name for arg in prompt.arguments
                         if arg.name not in template_args]

        # Check if all variables exist
        missing_vars = [var for var in required_vars if var not in variables]

        if missing_vars:
            # Mark session as waiting for input
            session.status = SessionStatus.WAITING_FOR_INPUT
            session.workflow_data.missing_variables.extend(missing_vars)
            return False

        return True

    async def handle(self, session: Session, step: Step) -> Dict[str, Any]:
        """Handle a prompt step"""
        if not isinstance(step, PromptStep):
            raise TypeError(f"Expected PromptStep but got {type(step)}")

        # Get prompt content
        prompt_content = await self._get_prompt_content(session, step)

        # Create a message in the database
        user_message = Message(
            id=uuid.uuid4(),
            session_id=session.id,
            role=step.role,
            text=prompt_content,
            status=MessageStatus.PENDING
        )
        
        # Add the user message to the session
        session.messages.append(user_message)
        
        # Create a placeholder for the assistant response
        assistant_message = Message(
            id=uuid.uuid4(),
            session_id=session.id,
            role="assistant",
            text="",
            status=MessageStatus.PENDING
        )
        
        # Add the assistant message to the session
        session.messages.append(assistant_message)
        
        # Process with LLM service
        result_message = await self.llm_service.complete(
            session,
            broadcast=self._create_broadcast_callback(session.id)
        )

        # Return step result
        return {
            'prompt': user_message,
            'response': result_message
        }
        
    def _create_broadcast_callback(self, session_id: uuid.UUID) -> Optional[Callable[[Message], Awaitable[None]]]:
        """Create a broadcast callback for streaming updates"""
        # This would be implemented to broadcast updates via SSE
        # For now, return None as we'll implement this later
        return None

    async def _get_prompt_content(self, session: Session, step: PromptStep) -> str | list:
        """Get the content for a prompt step"""
        if step.content is not None:
            return step.content

        if step.template is not None:
            # Get variables and template args
            variables = session.workflow_data.variables
            template_args = step.template_args or {}

            # Combine variables and template args
            args = {**variables, **template_args}

            # Get prompt from registry
            prompt = self.registry.get_prompt(step.template)

            return await prompt.render(args)

        return ""

