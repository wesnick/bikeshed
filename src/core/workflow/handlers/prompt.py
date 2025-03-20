from typing import Dict, Any, List, Optional, AsyncGenerator
import uuid

from src.core.config_types import PromptStep, Step
from src.core.registry import Registry
from src.models.models import Session, Message
from src.core.workflow.engine import StepHandler
from src.core.llm import LLMMessage, LLMMessageFactory


class PromptStepHandler(StepHandler):
    """Handler for prompt steps"""

    def __init__(self, registry: Registry, llm_service):
        """
        Initialize the PromptStepHandler
        
        Args:
            registry: Registry instance
            llm_service: Service for LLM interactions
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
        variables = session.workflow_data.get('variables', {})
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
            session.status = 'waiting_for_input'
            session.workflow_data['missing_variables'] = missing_vars
            return False

        return True

    async def handle(self, session: Session, step: Step) -> Dict[str, Any]:
        """Handle a prompt step"""
        if not isinstance(step, PromptStep):
            raise TypeError(f"Expected PromptStep but got {type(step)}")

        # Set status to running
        session.status = 'running'

        # Get prompt content
        prompt_content = await self._get_prompt_content(session, step)

        # Create messages for tracking
        db_messages = await self._create_prompt_messages(session, prompt_content)

        # Get system prompt if available
        system_prompt = None
        if session.workflow_data and 'variables' in session.workflow_data:
            system_prompt = session.workflow_data['variables'].get('system_prompt')

        # Convert to LLM messages
        llm_messages = LLMMessageFactory.from_session_messages(db_messages, system_prompt)

        # Call LLM service
        response = await self.llm_service.generate_response(llm_messages)

        # Create response message
        response_message = Message(
            id=uuid.uuid4(),
            session_id=session.id,
            role="assistant",
            text=response,
            status='delivered',
            parent_id=db_messages[-1].id if db_messages else None
        )

        # Add all messages to session data
        if not hasattr(session, '_temp_messages'):
            session._temp_messages = []

        session._temp_messages.extend(db_messages + [response_message])

        # Return step result
        return {
            'prompt_message_ids': [str(msg.id) for msg in db_messages],
            'response_message_id': str(response_message.id),
            'response': response
        }

    async def _get_prompt_content(self, session: Session, step: PromptStep) -> str | list:
        """Get the content for a prompt step"""
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

            return await prompt.render(args)

        return ""

    async def _create_prompt_messages(
            self, session: Session, prompt_content: str | list
    ) -> List[Message]:
        """Create messages for a prompt"""
        if isinstance(prompt_content, list):
            # Handle multi-part prompts
            messages = []
            parent_id = None

            for part in prompt_content:
                msg = Message(
                    id=uuid.uuid4(),
                    session_id=session.id,
                    role=part.role,
                    text=part.content.text,
                    mime_type=part.content.type,
                    status='delivered',
                    parent_id=parent_id
                )
                messages.append(msg)
                parent_id = msg.id

            return messages
        else:
            # Handle simple string prompt
            return [Message(
                id=uuid.uuid4(),
                session_id=session.id,
                role="user",
                text=prompt_content,
                status='delivered'
            )]
