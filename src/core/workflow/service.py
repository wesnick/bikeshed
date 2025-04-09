from typing import Dict, Any, Optional, Callable, AsyncGenerator
import uuid

from psycopg import AsyncConnection

from src.core.config_types import DialogTemplate
from src.core.registry import Registry
from src.core.models import Dialog, DialogStatus
from src.core.workflow.engine import WorkflowEngine, StepResult
from src.core.workflow.persistence import DatabasePersistenceProvider
from src.core.workflow.handlers.message import MessageStepHandler
from src.core.workflow.handlers.prompt import PromptStepHandler
from src.core.workflow.handlers.user_input import UserInputStepHandler
from src.core.workflow.handlers.invoke import InvokeStepHandler
from src.core.workflow.visualization import WorkflowVisualizer
from src.core.broadcast.broadcast import BroadcastService
from src.core.inference import CompletionService
from src.logging import logger

class WorkflowService:
    """Service for managing workflow state machines"""

    def __init__(self,
                 get_db: Callable[[], AsyncGenerator[AsyncConnection, None]],
                 registry: Registry,
                 completion_service: CompletionService,
                 broadcast_service: BroadcastService):
        """
        Initialize the WorkflowService with required dependencies.

        Args:
            get_db: async generator for getting database connection
            registry: Registry instance
        """
        # Create persistence provider
        self.persistence = DatabasePersistenceProvider(get_db)

        # Create step handlers
        self.handlers = {
            'message': MessageStepHandler(registry=registry, completion_service=completion_service),
            'prompt': PromptStepHandler(registry=registry, completion_service=completion_service),
            'user_input': UserInputStepHandler(registry=registry, completion_service=completion_service),
            'invoke': InvokeStepHandler(registry=registry, completion_service=completion_service)
        }

        # Create workflow engine
        self.engine = WorkflowEngine(self.persistence, self.handlers)
        self.registry = registry
        self.broadcast_service = broadcast_service


    async def create_dialog_from_template(
            self,
            template: DialogTemplate,
            description: Optional[str] = None,
            goal: Optional[str] = None,
            initial_data: Optional[Dict] = None
    ) -> Dialog:
        """Create a new dialog from a template"""
        # Create dialog data
        dialog_data = {
            "id": uuid.uuid4(),
            "description": description or template.description,
            "goal": goal or template.goal,
            "template": template,
            "status": DialogStatus.PENDING,
            "workflow_data": initial_data or {}
        }

        # Create dialog in database
        dialog = await self.persistence.create_dialog(dialog_data)

        # Initialize workflow
        await self.engine.initialize_dialog(dialog)

        return dialog

    async def get_dialog(self, dialog_id: uuid.UUID) -> Optional[Dialog]:
        """Get a dialog by ID and initialize its workflow"""
        dialog = await self.persistence.load_dialog(dialog_id)
        if not dialog:
            return None

        return await self.engine.initialize_dialog(dialog)

    async def run_workflow(self, dialog: Dialog) -> None:
        """Run the workflow until completion or waiting for input"""
        while True:
            # Broadcast dialog update
            await self.broadcast_service.broadcast("dialog.update", str(dialog.id))
            # Broadcast notification update
            await self.broadcast_service.broadcast("notifications.update", "refresh")

            exec_result = await self.engine.execute_next_step(dialog)

            # Broadcast dialog update
            await self.broadcast_service.broadcast("dialog.update", str(dialog.id))
            # Broadcast notification update
            await self.broadcast_service.broadcast("notifications.update", "refresh")

            if not exec_result.success or dialog.status == DialogStatus.WAITING_FOR_INPUT:
                break

    async def provide_missing_variables(
            self,
            dialog: Dialog,
            input_variables: dict[str, Any]
    ) -> StepResult:
        """Provide user input for a waiting step"""

        if dialog.status != DialogStatus.WAITING_FOR_INPUT:
            return StepResult.failure_result(
                state=dialog.current_state,
                message="Dialog is not waiting for input"
            )

        for key, value in input_variables.items():
            dialog.workflow_data.add_variable(key, value)

        # Change status if we still have missing variables
        if dialog.workflow_data.missing_variables:
            dialog.status = DialogStatus.WAITING_FOR_INPUT
            logger.warning(f"Still needed inputs: {dialog.workflow_data.missing_variables}")
        else:
            dialog.status = DialogStatus.PAUSED

        # Save changes
        await self.persistence.save_dialog(dialog)

        if dialog.status == DialogStatus.WAITING_FOR_INPUT:
            return StepResult.waiting_result(
                state=dialog.current_state,
                required_variables=dialog.workflow_data.missing_variables
            )

        return StepResult.success_result(
            state=dialog.status,
            message="Saved data to dialog"
        )


    async def provide_user_input(
            self,
            dialog: Dialog,
            user_input: str,
            request_completion: bool,
            resume_workflow: bool,
    ) -> StepResult:
        """Provide user input for a waiting step"""
        return await self.provide_missing_variables(dialog, {
            'user_input': user_input,
            'request_completion': request_completion,
            'resume_workflow': resume_workflow,
        })


    async def create_workflow_graph(self, dialog: Dialog) -> Optional[str]:
        """Create a visualization of the workflow"""
        return await WorkflowVisualizer.create_graph(dialog)

    async def visualize_workflow(self, dialog: Dialog) -> Optional[str]:
        """
        Generate a visual representation of the workflow

        Args:
            dialog: The dialog to visualize

        Returns:
            SVG representation of the workflow graph
        """
        # Make sure the dialog has a state machine
        if not hasattr(dialog, 'machine') or dialog.machine is None:
            await self.engine.initialize_dialog(dialog)

        return await WorkflowVisualizer.create_graph(dialog)

    async def analyze_workflow_dependencies(self, template: DialogTemplate) -> Dict[str, Any]:
        """
        Analyze a workflow template to identify input requirements and output provisions.

        Returns a dictionary with:
        - required_inputs: Dict of input variables needed by steps
        - provided_outputs: Dict of output variables provided by steps
        - missing_inputs: Dict of inputs not satisfied by previous steps
        """
        required_inputs = {}
        provided_outputs = {}
        missing_inputs = {}

        # Create a mock dialog for requirements analysis
        mock_dialog = Dialog(
            description="Mock dialog for analysis",
            template=template
        )
        await self.engine.initialize_dialog(mock_dialog)

        # Analyze each step for inputs and outputs
        for i, workflow_step in enumerate(mock_dialog._get_workflow_steps()):
            step = workflow_step.step
            if not step:
                continue

            step_id = step.name

            # Get the handler for this step type
            handler = self.handlers.get(step.type)
            if not handler:
                continue

            # Get requirements for this step
            requirements = await handler.get_step_requirements(mock_dialog, step)

            # Add required inputs
            if requirements.required_variables:
                required_inputs[step_id] = requirements.required_variables

                # Check if these inputs are satisfied by previous steps
                unsatisfied_inputs = {}
                for input_name, input_info in requirements.required_variables.items():
                    if not any(input_name in outputs for outputs in list(provided_outputs.values())):
                        unsatisfied_inputs[input_name] = input_info

                if unsatisfied_inputs:
                    missing_inputs[step_id] = unsatisfied_inputs

            # Add provided outputs
            if requirements.provided_outputs:
                provided_outputs[step_id] = requirements.provided_outputs

        return {
            "required_inputs": required_inputs,
            "provided_outputs": provided_outputs,
            "missing_inputs": missing_inputs
        }
