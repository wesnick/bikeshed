from typing import Dict, Any, Optional, Union, Callable, AsyncGenerator
import uuid

from psycopg import AsyncConnection

from src.core.config_types import DialogTemplate, Step
from src.core.registry import Registry
from src.core.models import Dialog, DialogStatus
from src.core.workflow.engine import WorkflowEngine, WorkflowTransitionResult
from src.core.workflow.persistence import DatabasePersistenceProvider
from src.core.workflow.handlers.message import MessageStepHandler
from src.core.workflow.handlers.prompt import PromptStepHandler
from src.core.workflow.handlers.user_input import UserInputStepHandler
from src.core.workflow.handlers.invoke import InvokeStepHandler
from src.core.workflow.visualization import WorkflowVisualizer
from src.service.broadcast import BroadcastService
from src.service.llm import CompletionService


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
            'message': MessageStepHandler(registry=registry),
            'prompt': PromptStepHandler(registry=registry, completion_service=completion_service),
            'user_input': UserInputStepHandler(),
            'invoke': InvokeStepHandler()
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
        return await self.engine.initialize_dialog(dialog)

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

    async def provide_user_input(
            self,
            dialog_id: uuid.UUID,
            user_input: str
    ) -> WorkflowTransitionResult:
        """Provide user input for a waiting step"""
        dialog = await self.get_dialog(dialog_id)
        if not dialog:
            return WorkflowTransitionResult(
                success=False,
                state="unknown",
                message=f"Dialog {dialog_id} not found"
            )

        if dialog.status != DialogStatus.WAITING_FOR_INPUT:
            return WorkflowTransitionResult(
                success=False,
                state=dialog.current_state,
                message="Dialog is not waiting for input"
            )

        # Handle different input types
        if dialog.workflow_data.has_missing_variables():
            # For variable inputs
            if not isinstance(user_input, dict):
                return WorkflowTransitionResult(
                    success=False,
                    state=dialog.current_state,
                    message="Expected dictionary for variable inputs"
                )

            # Update variables
            dialog.workflow_data.variables.update(user_input)

            # Clear missing variables flag
            dialog.workflow_data.variables.pop('missing_variables')
        else:
            # For user_input steps
            if dialog.workflow_data:
                dialog.workflow_data.variables['user_input'] = user_input

        # Save changes
        await self.persistence.save_dialog(dialog)

        # Execute next step
        return await self.engine.execute_next_step(dialog)

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

        # Analyze each step for inputs and outputs
        for i, step in enumerate(template.steps):
            step_id = step.name

            # Analyze step for required inputs
            step_inputs = self._extract_step_inputs(step)
            if step_inputs:
                required_inputs[step_id] = step_inputs

                # Check if these inputs are satisfied by previous steps
                unsatisfied_inputs = {}
                for input_name, input_info in step_inputs.items():
                    if not any(input_name in outputs for outputs in list(provided_outputs.values())):
                        unsatisfied_inputs[input_name] = input_info

                if unsatisfied_inputs:
                    missing_inputs[step_id] = unsatisfied_inputs

            # Analyze step for provided outputs
            step_outputs = self._extract_step_outputs(step)
            if step_outputs:
                provided_outputs[step_id] = step_outputs

        return {
            "required_inputs": required_inputs,
            "provided_outputs": provided_outputs,
            "missing_inputs": missing_inputs
        }

    def _extract_step_inputs(self, step: Step) -> Dict[str, Dict[str, Any]]:
        """Extract input requirements from a step"""
        inputs = {}

        # Extract based on step type
        if step.type == "prompt":
            if step.template:
                prompt = self.registry.get_prompt(step.template)
                if prompt and hasattr(prompt, 'arguments'):
                    for arg in prompt.arguments:
                        inputs[arg.name] = {
                            "description": arg.description,
                            "required": arg.required
                        }
            if step.template_args:
                for arg_name in step.template_args:
                    if arg_name in inputs:
                        inputs[arg_name]["description"] = inputs[arg_name]["description"] + ' (superseded by `template_args`)'
                        inputs[arg_name]["required"] = False

        elif step.type == "invoke":
            if step.args:
                for arg_name in step.args:
                    inputs[arg_name] = {
                        "description": f"Input for function argument: {arg_name}",
                        "required": True
                    }

        elif step.type == "user_input":
            # User input steps themselves don't require inputs, they provide them
            pass

        elif step.type == "message":
            if step.template_args:
                for arg_name in step.template_args:
                    inputs[arg_name] = {
                        "description": f"Input for message template argument: {arg_name}",
                        "required": True
                    }

        return inputs

    def _extract_step_outputs(self, step: Step) -> Dict[str, Dict[str, Any]]:
        """Extract outputs provided by a step"""
        outputs = {}

        # Extract based on step type
        if step.type == "prompt":
            outputs["result"] = {
                "description": f"Output from prompt step: {step.name}",
                "source_step": step.name
            }

        elif step.type == "invoke":
            outputs["result"] = {
                "description": f"Output from function call: {step.name}",
                "source_step": step.name
            }

        elif step.type == "user_input":
            outputs["user_input"] = {
                "description": f"User provided input from step: {step.name}",
                "source_step": step.name
            }

        return outputs
