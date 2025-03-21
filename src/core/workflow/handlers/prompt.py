from typing import Dict, Any

from src.core.config_types import PromptStep, Step
from src.core.registry import Registry
from src.models.models import Session
from src.core.workflow.engine import StepHandler
from src.core.llm.llm import LLMService


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

        # Create conversation manager with middleware chain
        from src.core.llm.manager import ConversationManager, MessageContext
        from src.core.llm.middleware import (
            MessagePersistenceMiddleware,
            LLMProcessingMiddleware,
            TemplateProcessingMiddleware
        )
        
        manager = ConversationManager([
            TemplateProcessingMiddleware(self.registry),
            MessagePersistenceMiddleware(),
            LLMProcessingMiddleware(self.llm_service)
        ])
        
        # Get prompt content
        prompt_content = await self._get_prompt_content(session, step)
        
        # Process through middleware chain
        context = await manager.process(MessageContext(
            session=session,
            raw_input=prompt_content,
            metadata={"step": step.model_dump() if hasattr(step, "model_dump") else vars(step)}
        ))
        
        # Extract created messages
        messages = context.metadata.get("messages", [])
        prompt_messages = [msg for msg in messages if msg.role == "user"]
        response_message = next((msg for msg in messages if msg.role == "assistant"), None)
        
        # Return step result
        return {
            'prompt_message_ids': [str(msg.id) for msg in prompt_messages],
            'response_message_id': str(response_message.id) if response_message else None,
            'response': context.output
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

