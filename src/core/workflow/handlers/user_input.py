from src.core.workflow.handlers import BaseStepHandler
from src.core.workflow.engine import StepResult
from src.core.config_types import UserInputStep, Step
from src.core.models import Dialog, Message, DialogStatus, MessageStatus, WorkflowData
from src.service.llm import CompletionService
from src.service.logging import logger

class UserInputStepHandler(BaseStepHandler):
    """Handler for user_input steps"""

    async def can_handle(self, dialog: Dialog, step: Step) -> bool:
        """Check if the step can be handled"""
        if not isinstance(step, UserInputStep):
            return False

        if dialog.workflow_data.needs_user_input():
            logger.debug(f"User input for step {step.name} was is needed")
            return False

        return True


    async def handle(self, dialog: Dialog, step: Step) -> StepResult:
        """Handle a user_input step"""
        if not isinstance(step, UserInputStep):
            raise TypeError(f"Expected UserInputStep but got {type(step)}")

        # Get the user input from workflow data
        workflow_data: WorkflowData = dialog.workflow_data
        user_input = workflow_data.variables.get('user_input')

        if not user_input:
            # If no user input is available, set status to waiting and exit
            logger.warning(f"No user input found")
            dialog.status = DialogStatus.WAITING_FOR_INPUT
            return StepResult.waiting_result(
                state=dialog.current_state,
                required_variables=['user_input']
            )

        # Create a message for the user input using helper method
        dialog.create_user_message(user_input)

        # Clear the user_input after processing
        del workflow_data.variables['user_input']

        model = step.config_extra.get('model') or dialog.template.model
        # Create a placeholder for the assistant response using helper method
        dialog.create_stub_assistant_message(model)

        # Process with LLM service
        result_message = await self.completion_service.complete(
            dialog,
            broadcast=None
        )

        # Update status to running
        dialog.status = DialogStatus.RUNNING

        # Return step result
        return StepResult.success_result(
            state=dialog.current_state
        )
