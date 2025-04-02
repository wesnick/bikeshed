import uuid
from typing import Dict, Any

from mcp.server.fastmcp.prompts.base import Message as MCPMessage

from src.core.config_types import PromptStep, Step
from src.core.registry import Registry, TemplatePrompt
from src.core.models import Message
from src.core.models import Dialog, DialogStatus, MessageStatus
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


    async def can_handle(self, dialog: Dialog, step: Step) -> bool:
        """Check if the step can be handled"""
        if not isinstance(step, PromptStep):
            return False

        # If no template, no variables needed
        if not step.template:
            return True

        # Check all required variables
        variables = dialog.workflow_data.variables
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
            # Mark dialog as waiting for input
            dialog.status = DialogStatus.WAITING_FOR_INPUT
            dialog.workflow_data.missing_variables.extend(missing_vars)
            return False

        return True

    async def handle(self, dialog: Dialog, step: Step) -> Dict[str, Any]:
        """Handle a prompt step"""
        if not isinstance(step, PromptStep):
            raise TypeError(f"Expected PromptStep but got {type(step)}")

        # Get prompt content
        prompt_content = await self._get_prompt_content(dialog, step)
        model = step.config_extra.get('model') or dialog.template.model

        step_messages = []

        if isinstance(prompt_content, str):
            # Create a message in the database
            user_message = Message(
                id=uuid.uuid4(),
                dialog_id=dialog.id,
                role='user',
                text=prompt_content,
                status=MessageStatus.PENDING
            )

            # Add the user message to the dialog
            dialog.messages.append(user_message)
            step_messages.append(user_message)

        elif isinstance(prompt_content, list):
            for prompt in prompt_content:
                message = Message(
                    id=uuid.uuid4(),
                    dialog_id=dialog.id,
                    role=prompt.role,
                    model=model if prompt.role == 'assistant' else None,
                    text=prompt.content.text,
                    status=MessageStatus.PENDING
                )

                # Add the user message to the dialog
                dialog.messages.append(message)
                step_messages.append(message)

        # Create a placeholder for the assistant response
        assistant_message = Message(
            id=uuid.uuid4(),
            model=model,
            dialog_id=dialog.id,
            role="assistant",
            text="",
            status=MessageStatus.CREATED
        )

        # Add the assistant message to the dialog
        dialog.messages.append(assistant_message)

        # Process with LLM service
        result_message = await self.completion_service.complete(
            dialog,
            broadcast=None
        )

        # Return step result
        return {
            'prompt': step_messages,
            'response': result_message
        }


    async def _get_prompt_content(self, dialog: Dialog, step: PromptStep) -> str | list[MCPMessage]:
        """Get the content for a prompt step"""
        if step.content is not None:
            return step.content

        if step.template is not None:
            # Get variables and template args
            variables = dialog.workflow_data.variables
            template_args = step.template_args or {}

            # Combine variables and template args
            args = {**variables, **template_args}

            # Get prompt from registry
            prompt = self.registry.get_prompt(step.template)

            if not prompt:
                raise ValueError(f"Prompt template '{step.template}' not found")

            if isinstance(prompt, TemplatePrompt):
                # Add template_content to args
                args['template_raw'] = prompt.template_content
                args['template_path'] = prompt.template_path

            return await prompt.render(args)

        return ""

