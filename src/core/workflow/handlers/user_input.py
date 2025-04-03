from typing import Any, Dict
import uuid

from src.core.workflow.engine import StepHandler
from src.core.config_types import UserInputStep, Step
from src.core.models import Dialog, Message, DialogStatus, MessageStatus, WorkflowData
from src.service.llm import CompletionService
from src.service.logging import logger

class UserInputStepHandler(StepHandler):
    """Handler for user_input steps"""

    def __init__(self, completion_service: CompletionService):
        """
        Initialize the UserInputStepHandler

        Args:
            completion_service: Optional CompletionService instance
        """
        self.completion_service = completion_service
    async def can_handle(self, dialog: Dialog, step: Step) -> bool:
        """Check if the step can be handled"""
        if not isinstance(step, UserInputStep):
            return False

        if dialog.workflow_data.needs_user_input():
            logger.debug(f"User input for step {step.name} was is needed")
            return False

        return True


    async def handle(self, dialog: Dialog, step: Step) -> Dict[str, Any]:
        """Handle a user_input step"""
        if not isinstance(step, UserInputStep):
            raise TypeError(f"Expected UserInputStep but got {type(step)}")

        # Get the user input from workflow data
        workflow_data: WorkflowData = dialog.workflow_data
        user_input = workflow_data.variables['user_input']

        if not user_input:
            # If no user input is available, set status to waiting and exit
            logger.warning(f"No user input found")
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
        del workflow_data.variables['user_input']

        model = step.config_extra.get('model') or dialog.template.model
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

        # Update status to running
        dialog.status = DialogStatus.RUNNING

        # Return step result
        return {
            'completed': True
        }
