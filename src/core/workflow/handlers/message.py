from typing import Any, Dict, AsyncGenerator
import uuid

from src.core.registry import Registry
from src.core.workflow.engine import StepHandler
from src.core.config_types import MessageStep, Step
from src.models.models import Session, Message, MessageStatus, SessionStatus


class MessageStepHandler(StepHandler):
    """Handler for message steps"""

    def __init__(self, registry: Registry):
        """
        Initialize the MessageStepHandler
        
        Args:
            registry: Registry instance
        """
        self.registry = registry

    async def can_handle(self, session: Session, step: Step) -> bool:
        """Check if the step can be handled"""
        return isinstance(step, MessageStep)

    async def handle(self, session: Session, step: Step) -> Dict[str, Any]:
        """Handle a message step"""
        if not isinstance(step, MessageStep):
            raise TypeError(f"Expected MessageStep but got {type(step)}")

        # Set status to running
        session.status = SessionStatus.RUNNING

        # Determine the message content based on the step configuration
        message_content = await self._get_message_content(session, step)

        # Create a message in the database
        message = Message(
            id=uuid.uuid4(),
            session_id=session.id,
            role=step.role,
            text=message_content,
            status=MessageStatus.CREATED
        )

        # Return step result
        return {
            'message_id': str(message.id),
            'content': message_content
        }

    async def _get_message_content(self, session: Session, step: MessageStep) -> str:
        """Get the content for a message step"""
        if step.content is not None:
            return step.content

        if step.template is not None:
            # Get variables and template args
            variables = session.workflow_data.get('variables', {})
            template_args = step.template_args or {}

            # Combine variables and template args
            args = {**variables, **template_args}

            # Get prompt from registry
            prompt = self.registry.get_prompt(step.template)

            # @TODO: fix me, prompt is a list here
            return await prompt.render(args)

        return ""
