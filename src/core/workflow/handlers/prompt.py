import uuid
from typing import Dict, Any

from src.core.config_types import PromptStep, Step
from src.core.registry import Registry
from src.models import Message
from src.models.models import Session, SessionStatus, MessageStatus
from src.core.workflow.engine import StepHandler


class PromptStepHandler(StepHandler):
    """Handler for prompt steps"""

    def __init__(self, registry: Registry):
        """
        Initialize the PromptStepHandler
        
        Args:
            registry: Registry instance
        """
        self.registry = registry

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
        
        # TODO: send to llm get result
        result_message = None

        # Return step result
        return {
            'prompt': user_message,
            'response': result_message
        }

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

