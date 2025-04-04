from src.core.workflow.handlers import BaseStepHandler
from src.core.workflow.engine import StepResult
from src.core.config_types import MessageStep, Step
from src.core.models import Dialog, Message, MessageStatus, DialogStatus


class MessageStepHandler(BaseStepHandler):
    """Handler for message steps"""

    async def can_handle(self, dialog: Dialog, step: Step) -> bool:
        """Check if the step can be handled"""
        return isinstance(step, MessageStep)

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
