from typing import Dict, Any, List, Optional, AsyncGenerator
import uuid

from src.core.config_types import PromptStep, Step
from src.core.registry import Registry
from src.models.models import Session, Message
from src.core.workflow.engine import StepHandler
from src.core.llm import LLMMessage, LLMMessageFactory, LLMService
from src.core.llm_response import LLMResponseHandler


class PromptStepHandler(StepHandler):
    """Handler for prompt steps"""

    def __init__(self, registry: Registry, llm_service: LLMService):
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

        # Convert to LLM messages
        llm_messages = LLMMessageFactory.from_session_messages(session, [])
        
        # Add the prompt content
        if isinstance(prompt_content, list):
            # Handle multi-part prompts by converting to LLMMessages
            for part in prompt_content:
                llm_messages.append(LLMMessage(
                    role=part.role,
                    content=part.content.text
                ))
        else:
            # Add simple string prompt
            llm_messages.append(LLMMessage.user(prompt_content))

        # Call LLM service
        response = await self.llm_service.generate_response(llm_messages)

        # Use the new handler to process the interaction
        prompt_messages, response_message = await LLMResponseHandler.process_llm_interaction(
            session=session,
            prompt_content=prompt_content,
            response_text=response
        )

        # Return step result
        return {
            'prompt_message_ids': [str(msg.id) for msg in prompt_messages],
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

