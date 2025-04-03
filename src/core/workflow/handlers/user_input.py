from typing import Any, Dict
import uuid

from src.core.workflow.engine import StepHandler
from src.core.config_types import UserInputStep, Step
from src.core.models import Dialog, Message, DialogStatus, MessageStatus
from src.service.logging import logger

class UserInputStepHandler(StepHandler):
    """Handler for user_input steps"""

    async def can_handle(self, dialog: Dialog, step: Step) -> bool:
        """Check if the step can be handled"""
        if not isinstance(step, UserInputStep):
            return False

        if not dialog.workflow_data.needs_user_input():
            # Mark dialog as waiting for input
            logger.warning("User input needs, so marking as needing input.  @TODO: can_handle should not change state")

            dialog.status = DialogStatus.WAITING_FOR_INPUT
            dialog.workflow_data.missing_variables.append('user_input')
            return False

        return True


    async def handle(self, dialog: Dialog, step: Step) -> Dict[str, Any]:
        """Handle a user_input step"""
        if not isinstance(step, UserInputStep):
            raise TypeError(f"Expected UserInputStep but got {type(step)}")

        # Get the user input from workflow data
        user_input = dialog.workflow_data.get('user_input')

        if not user_input:
            # If no user input is available, set status to waiting and exit
            dialog.status = DialogStatus.WAITING_FOR_INPUT
            return {'completed': False, 'waiting_for_input': True}

        # Create a message for the user input
        message = Message(
            id=uuid.uuid4(),
            dialog_id=dialog.id,
            role="user",
            text=user_input,
            status=MessageStatus.CREATED
        )

        dialog.messages.append(message)

        # Clear the user_input after processing
        dialog.workflow_data.pop('user_input', None)

        # Update status to running
        dialog.status = DialogStatus.RUNNING

        # Return step result
        return {
            'message_id': str(message.id),
            'input': user_input,
            'completed': True
        }
