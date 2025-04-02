from typing import Dict, List, Optional, Protocol, Any, Tuple
import uuid
from transitions.extensions import AsyncGraphMachine
from dataclasses import dataclass

from src.core.config_types import Step, DialogTemplate
from src.core.workflow.visualization import BikeShedState
from src.core.models import Dialog, DialogStatus
from src.service.logging import logger


class StepHandler(Protocol):
    """Protocol defining the interface for step handlers"""
    async def can_handle(self, dialog: Dialog, step: Step) -> bool: ...
    async def handle(self, dialog: Dialog, step: Step) -> Dict[str, Any]: ...

class PersistenceProvider(Protocol):
    """Protocol defining the interface for persistence providers"""
    async def save_dialog(self, dialog: Dialog) -> None: ...
    async def load_dialog(self, dialog_id: uuid.UUID) -> Optional[Dialog]: ...

@dataclass
class WorkflowTransitionResult:
    """Result of a workflow transition"""
    success: bool
    state: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    waiting_for_input: bool = False
    required_variables: Optional[List[str]] = None

class WorkflowEngine:
    """Engine for executing workflow state machines"""

    def __init__(
        self,
        persistence_provider: PersistenceProvider,
        handlers: Dict[str, StepHandler]
    ):
        self.persistence = persistence_provider
        self.handlers = handlers

    async def initialize_dialog(self, dialog: Dialog) -> Dialog:
        """Initialize a state machine for a dialog"""
        if isinstance(dialog.machine, AsyncGraphMachine):
            return dialog

        if not dialog.template:
            raise ValueError("Dialog must have a template")

        # Extract states and transitions
        states, transitions = self._build_state_machine_config(dialog.template)

        # Create state machine
        machine = AsyncGraphMachine(
            model=dialog,
            states=states,
            initial=dialog.current_state or 'start',
            send_event=True,
            auto_transitions=False,
            model_attribute='current_state',
            after_state_change=self._after_state_change,
        )

        for transition in transitions:
            machine.add_transition(**transition)


        dialog.machine = machine

        return dialog

    def _build_state_machine_config(self, template: DialogTemplate) -> Tuple[List, List]:
        """Build states and transitions config for state machine"""
        # Create start and end states with custom labels
        states = [
            BikeShedState('start', label='Start'),
            BikeShedState('end', label='End', final=True)
        ]
        transitions = []

        enabled_steps = [step for step in template.steps if step.enabled]

        for i, step in enumerate(enabled_steps):
            # Add state with step data for better visualization
            state_name = f'step_{i}'
            state = BikeShedState(state_name, step_data=step)
            states.insert(len(states) - 1, state)

            # Add transition to this state with step data for better visualization
            source = 'start' if i == 0 else f'step_{i-1}'

            transition = {
                'trigger': f'run_{state_name}',
                'source': source,
                'dest': state_name,
                'before': self._execute_step,
                'conditions': self._can_execute_step,
            }
            transitions.append(transition)

            # Add final transition if this is the last step
            if i == len(enabled_steps) - 1:
                transitions.append({
                    'trigger': 'finalize',
                    'source': state_name,
                    'dest': 'end',
                    'before': self._finalize_workflow,
                    # 'label': 'Complete'
                })

        return states, transitions

    async def _after_state_change(self, event):
        """Handle state change events"""
        dialog = event.model
        await self.persistence.save_dialog(dialog)

    async def _can_execute_step(self, event):
        """Check if a step can be executed"""
        dialog = event.model
        next_step = await self.get_current_step(dialog)

        if not next_step:
            return False

        handler = self.handlers.get(next_step.type)
        if not handler:
            return False

        return await handler.can_handle(dialog, next_step)

    async def _execute_step(self, event):
        """Execute the current step"""
        dialog = event.model
        next_step = await self.get_current_step(dialog)

        if not next_step:
            return

        handler = self.handlers.get(next_step.type)
        if not handler:
            dialog.workflow_data.errors.append(f"No handler for step type: {next_step.type}")
            return

        try:
            result = await handler.handle(dialog, next_step)

            # Update workflow data
            dialog.workflow_data.current_step_index += 1
            dialog.workflow_data.step_results[next_step.name] = {
                'completed': True,
                **result
            }

        except Exception as e:
            dialog.workflow_data.errors.append(str(e))
            dialog.status = 'error'
            raise e

    async def _finalize_workflow(self, event):
        """Finalize the workflow"""
        dialog = event.model
        dialog.status = 'completed'

    async def get_current_step(self, dialog: Dialog) -> Optional[Step]:
        """Get the current step to execute"""
        if not dialog.template:
            return None

        enabled_steps = [step for step in dialog.template.steps if step.enabled]
        current_index = dialog.workflow_data.current_step_index

        if current_index < len(enabled_steps):
            return enabled_steps[current_index]
        return None

    async def execute_next_step(self, dialog: Dialog) -> WorkflowTransitionResult:
        """Execute the next step in the workflow"""
        next_step = await self.get_current_step(dialog)
        if not next_step:
            # No more steps to execute
            result = WorkflowTransitionResult(
                success=False,
                state=dialog.current_state,
                message="No more steps to execute"
            )
            # Ensure dialog is saved even when there are no more steps
            await self.persistence.save_dialog(dialog)
            return result

        # Find the trigger for this step
        trigger_name = f'run_step_{dialog.workflow_data.current_step_index}'

        # Check if the trigger exists
        if hasattr(dialog, trigger_name):
            trigger_method = getattr(dialog, trigger_name)

            try:
                await trigger_method()

                # Check if we're waiting for input
                if dialog.status == 'waiting_for_input':
                    missing_vars = dialog.workflow_data.missing_variables
                    await self.persistence.save_dialog(dialog)
                    return WorkflowTransitionResult(
                        success=False,
                        state=dialog.current_state,
                        waiting_for_input=True,
                        required_variables=missing_vars,
                        message=f"Waiting for input: {missing_vars}"
                    )


                return WorkflowTransitionResult(
                    success=True,
                    state=dialog.current_state,
                    message="Step executed successfully"
                )

            except Exception as e:
                logger.error(f"Error executing step: {str(e)}")
                # Save error state to workflow data
                dialog.workflow_data.errors.append(str(e))
                dialog.status = DialogStatus.FAILED
                # Ensure dialog is saved when an exception occurs
                await self.persistence.save_dialog(dialog)
                return WorkflowTransitionResult(
                    success=False,
                    state=dialog.current_state,
                    message=f"Error executing step: {str(e)}"
                )

        # Trigger not found
        result = WorkflowTransitionResult(
            success=False,
            state=dialog.current_state,
            message=f"Trigger {trigger_name} not found"
        )
        # Ensure dialog is saved even when trigger is not found
        await self.persistence.save_dialog(dialog)
        return result
