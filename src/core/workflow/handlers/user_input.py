from src.core.workflow.handlers.base import StepHandler, StepResult, StepRequirements
from src.core.config_types import UserInputStep, Step
from src.core.models import Dialog, DialogStatus, WorkflowData
from src.logging import logger

class UserInputStepHandler(StepHandler):
    """Handler for user_input steps"""

    async def get_step_requirements(self, dialog: Dialog, step: Step) -> StepRequirements:
        """Get the requirements for a user input step"""
        requirements = StepRequirements()

        if not isinstance(step, UserInputStep):
            return requirements

        # Add the user_input as a required variable
        requirements.add_required_variable(
            "user_input",
            "User input required for this step",
            True,
            str,
        )
        requirements.add_required_variable(
            "resume_workflow",
            "Whether to continue the workflow",
            True,
            bool
        )
        requirements.add_required_variable(
            "request_completion",
            "Whether to request a completion from an LLM after for the given user input",
            True,
            bool
        )

        return requirements


    async def handle(self, dialog: Dialog, step: Step) -> StepResult:
        """Handle a user_input step"""
        if not isinstance(step, UserInputStep):
            raise TypeError(f"Expected UserInputStep but got {type(step)}")

        # Get the user input from workflow data
        workflow_data: WorkflowData = dialog.workflow_data
        user_input = workflow_data.variables.get('user_input')

        if not user_input:
            # If no user input is available, set status to waiting and exit
            logger.warning("No user input found")
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
        await self.completion_service.complete(
            dialog,
            broadcast=None
        )

        # Update status to running
        dialog.status = DialogStatus.RUNNING

        # Return step result
        return StepResult.success_result(
            state=dialog.current_state
        )
