from src.core.workflow.handlers import BaseStepHandler
from src.core.workflow.engine import StepResult
from src.core.config_types import MessageStep, Step
from src.core.models import Dialog, Message, MessageStatus, DialogStatus


class MessageStepHandler(BaseStepHandler):
    """Handler for message steps"""

    async def get_step_requirements(self, dialog: Dialog, step: Step) -> StepRequirements:
        """Get the requirements for a message step"""
        requirements = StepRequirements()
        
        if not isinstance(step, MessageStep):
            return requirements
            
        # Check for template args
        if hasattr(step, 'template_args') and step.template_args:
            for arg_name in step.template_args:
                requirements.add_required_variable(
                    arg_name,
                    f"Input for message template argument: {arg_name}",
                    True
                )
                
        return requirements

    async def handle(self, dialog: Dialog, step: Step) -> StepResult:
        """Handle a message step"""
        await self.validate_step_type(step, MessageStep)

        message_content = await self.prepare_prompt_content(dialog, step)

        dialog.create_message(
            role=step.role,
            text=message_content,
            status=MessageStatus.CREATED
        )

        return StepResult.success_result(
            state=dialog.current_state,
        )
