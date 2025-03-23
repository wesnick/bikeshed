import uuid
from typing import Dict, Any

from mcp.server.fastmcp.prompts.base import Message as MCPMessage

from src.core.config_types import PromptStep, Step
from src.core.registry import Registry
from src.models import Message
from src.models.models import Session, SessionStatus, MessageStatus
from src.core.workflow.engine import StepHandler
from src.service.llm import CompletionService


class PromptStepHandler(StepHandler):
    """Handler for prompt steps"""

    def __init__(self, registry: Registry,
                 completion_service: CompletionService):
        """
        Initialize the PromptStepHandler
        
        Args:
            registry: Registry instance
            completion_service: Optional CompletionService instance
        """
        self.registry = registry
        self.completion_service = completion_service


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

        step_messages = []

        if isinstance(prompt_content, str):
            # Create a message in the database
            user_message = Message(
                id=uuid.uuid4(),
                session_id=session.id,
                role='user',
                text=prompt_content,
                status=MessageStatus.PENDING
            )
        
            # Add the user message to the session
            session.messages.append(user_message)
            step_messages.append(user_message)

        elif isinstance(prompt_content, list):
            for prompt in prompt_content:
                message = Message(
                    id=uuid.uuid4(),
                    session_id=session.id,
                    role=prompt.role,
                    text=prompt.content.text,
                    status=MessageStatus.PENDING
                )

                # Add the user message to the session
                session.messages.append(message)
                step_messages.append(message)

        
        # Create a placeholder for the assistant response
        assistant_message = Message(
            id=uuid.uuid4(),
            session_id=session.id,
            role="assistant",
            text="",
            status=MessageStatus.CREATED
        )

        # Add the assistant message to the session
        session.messages.append(assistant_message)
        
        # Process with LLM service
        result_message = await self.completion_service.complete(
            session,
            broadcast=None
        )

        # Return step result
        return {
            'prompt': step_messages,
            'response': result_message
        }


    async def _get_prompt_content(self, session: Session, step: PromptStep) -> str | list[MCPMessage]:
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

