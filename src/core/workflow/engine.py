from typing import Dict, List, Optional, Protocol, Tuple
import uuid

from transitions.extensions import AsyncGraphMachine

from src.core.config_types import DialogTemplate
from src.core.workflow.handlers.base import StepHandler, StepResult

from src.core.workflow.visualization import BikeShedState
from src.core.models import Dialog, DialogStatus
from src.logging import logger

class PersistenceProvider(Protocol):
    """Protocol defining the interface for persistence providers"""
    async def save_dialog(self, dialog: Dialog) -> None: ...
    async def load_dialog(self, dialog_id: uuid.UUID) -> Optional[Dialog]: ...

class WorkflowEngine:
    """Engine for executing workflow state machines"""

    def __init__(
        self,
        persistence_provider: PersistenceProvider,
        handlers: Dict[str, StepHandler]
    ):
        self.persistence = persistence_provider
        self.handlers = handlers

    async def initialize_dialog(self, dialog: Dialog):
        """Initialize a state machine for a dialog"""
        if isinstance(dialog.machine, AsyncGraphMachine):
            return

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
                })

        return states, transitions

    async def _after_state_change(self, event):
        """Handle state change events"""
        dialog = event.model
        await self.persistence.save_dialog(dialog)

    async def _can_execute_step(self, event):
        """Check if a step can be executed"""
        dialog = event.model
        current_workflow_step = dialog.get_current_workflow_step()

        if not current_workflow_step:
            return False

        handler = self.handlers.get(current_workflow_step.step.type)
        if not handler:
            dialog.workflow_data.errors.append(f"No handler for step type: {current_workflow_step.step.type}")
            # @TODO check where this is persisted
            return False

        logger.debug(f"[workflow] Checking if step {current_workflow_step.step.name} can be executed")

        # Get step requirements
        requirements = await handler.get_step_requirements(dialog, current_workflow_step.step)

        # Check if step can run with current variables
        can_run = requirements.can_run(await handler.prepare_arguments(dialog, current_workflow_step.step))

        if not can_run:
            # Update missing variables in workflow data
            dialog.workflow_data.missing_variables = requirements.get_missing_variables()
            dialog.status = DialogStatus.WAITING_FOR_INPUT
            # @TODO check where this is persisted

        return can_run

    async def _execute_step(self, event):
        """Execute the current step"""
        dialog = event.model
        current_workflow_step = dialog.get_current_workflow_step()

        if not current_workflow_step:
            return

        handler = self.handlers.get(current_workflow_step.step.type)
        if not handler:
            dialog.workflow_data.errors.append(f"No handler for step type: {current_workflow_step.step.type}")
            return

        try:
            result = await handler.handle(dialog, current_workflow_step.step)

            logger.debug(f"[workflow] Step {current_workflow_step.step.name} executed successfully: {result}")

            # Update workflow data
            dialog.workflow_data.step_results[current_workflow_step.step.name] = {
                'completed': result.success,
                **result.data
            }

        except Exception as e:
            dialog.workflow_data.errors.append(str(e))
            dialog.status = 'error'
            raise e

    async def _finalize_workflow(self, event):
        """Finalize the workflow"""
        dialog = event.model
        dialog.status = 'completed'

    async def execute_next_step(self, dialog: Dialog) -> StepResult:
        """Execute the next step in the workflow"""
        current_workflow_step = dialog.get_current_workflow_step()
        if not current_workflow_step:
            # No more steps to execute
            result = StepResult.failure_result(
                state=dialog.current_state,
                message="No more steps to execute"
            )
            # Ensure dialog is saved even when there are no more steps
            await self.persistence.save_dialog(dialog)
            return result

        # Find the trigger for this step
        trigger_name = current_workflow_step.trigger

        logger.debug(f"[workflow] Executing step {trigger_name}")

        # Check if the trigger exists
        if hasattr(dialog, trigger_name):
            trigger_method = getattr(dialog, trigger_name)

            try:
                await trigger_method()

                logger.debug(f"[workflow] Executing step {trigger_name}")

                # Check if we're waiting for input
                if dialog.status == 'waiting_for_input':
                    missing_vars = dialog.workflow_data.missing_variables
                    await self.persistence.save_dialog(dialog)
                    return StepResult.waiting_result(
                        state=dialog.current_state,
                        required_variables=missing_vars
                    )

                return StepResult.success_result(
                    state=dialog.current_state
                )

            except Exception as e:
                logger.error(f"Error executing step: {str(e)}")
                # Save error state to workflow data
                dialog.workflow_data.errors.append(str(e))
                dialog.status = DialogStatus.FAILED
                # Ensure dialog is saved when an exception occurs
                await self.persistence.save_dialog(dialog)
                return StepResult.failure_result(
                    state=dialog.current_state,
                    message=f"Error executing step: {str(e)}"
                )

        # Trigger not found
        result = StepResult.failure_result(
            state=dialog.current_state,
            message=f"Trigger {trigger_name} not found"
        )
        # Ensure dialog is saved even when trigger is not found
        await self.persistence.save_dialog(dialog)
        return result

