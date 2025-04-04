from src.core.config_types import PromptStep, Step
from src.core.models import Dialog, DialogStatus, MessageStatus
from src.core.workflow.handlers import BaseStepHandler
from src.core.workflow.engine import StepResult


class PromptStepHandler(BaseStepHandler):
    """Handler for prompt steps"""

    async def can_handle(self, dialog: Dialog, step: Step) -> bool:
        """Check if the step can be handled"""
        if not isinstance(step, PromptStep):
            return False

        # If no template, no variables needed
        if not step.template:
            return True

        # Check all required variables
        existing_vars = await self.prepare_arguments(dialog, step)

        # Get prompt from registry
        prompt = self.registry.get_prompt(step.template)

        if not prompt:
            raise ValueError(f"Prompt template '{step.template}' not found")

        required_vars = [arg.name for arg in prompt.arguments]

        # Check if all variables exist
        missing_vars = [var for var in required_vars if var not in existing_vars.keys()]

        if missing_vars:
            # Mark dialog as waiting for input
            dialog.status = DialogStatus.WAITING_FOR_INPUT
            dialog.workflow_data.missing_variables.extend(missing_vars)
            return False

        return True

    async def handle(self, dialog: Dialog, step: Step) -> StepResult:
        """Handle a prompt step"""
        await self.validate_step_type(step, PromptStep)

        # Get prompt content
        prompt_content = await self.prepare_prompt_content(dialog, step)
        model = step.config_extra.get('model') or dialog.template.model

        if isinstance(prompt_content, str):
            # Create a message using the helper method
            user_message = dialog.create_user_message(prompt_content)

        elif isinstance(prompt_content, list):
            for prompt in prompt_content:
                dialog.create_message(
                    role=prompt.role,
                    text=prompt.content.text,
                    model=model if prompt.role == 'assistant' else None,
                    status=MessageStatus.PENDING
                )

        # Create a placeholder for the assistant response
        dialog.create_stub_assistant_message(model)

        # Process with LLM service
        result_message = await self.completion_service.complete(
            dialog,
            broadcast=None
        )

        # Return step result
        return StepResult.success_result(
            state=dialog.current_state,
            data={
                'response': result_message
            }
        )




