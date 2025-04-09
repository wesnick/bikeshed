from src.core.config_types import PromptStep, Step
from src.core.models import Dialog, MessageStatus
from src.core.workflow.handlers.base import StepHandler, StepResult, StepRequirements


class PromptStepHandler(StepHandler):
    """Handler for prompt steps"""

    async def get_step_requirements(self, dialog: Dialog, step: Step) -> StepRequirements:
        """Get the requirements for a prompt step"""
        requirements = StepRequirements()

        if not isinstance(step, PromptStep):
            return requirements

        # If no template, no variables needed
        if not step.template:
            return requirements

        # Get prompt from registry
        prompt = self.registry.get_prompt(step.template)

        if not prompt:
            raise ValueError(f"Prompt template '{step.template}' not found")

        # Add required variables from prompt arguments
        for arg in prompt.arguments:
            # Check if this argument is overridden in template_defaults
            is_overridden = step.template_defaults and arg.name in step.template_defaults

            requirements.add_required_variable(
                arg.name,
                arg.description,
                required=arg.required and not is_overridden,
                datatype=str
            )

        return requirements

    async def handle(self, dialog: Dialog, step: Step) -> StepResult:
        """Handle a prompt step"""
        await self.validate_step_type(step, PromptStep)

        # Get prompt content
        prompt_content = await self.prepare_prompt_content(dialog, step)
        model = step.config_extra.get('model') or dialog.template.model

        if isinstance(prompt_content, str):
            # Create a message using the helper method
            dialog.create_user_message(prompt_content)

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




