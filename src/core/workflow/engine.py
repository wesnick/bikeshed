from typing import Dict, List, Optional, Type, Protocol, Any, TypeVar
import uuid
from transitions.extensions import AsyncGraphMachine
from dataclasses import dataclass

from src.core.config_types import Step, SessionTemplate
from src.models.models import Session

class StepHandler(Protocol):
    """Protocol defining the interface for step handlers"""
    async def can_handle(self, session: Session, step: Step) -> bool: ...
    async def handle(self, session: Session, step: Step) -> Dict[str, Any]: ...

class PersistenceProvider(Protocol):
    """Protocol defining the interface for persistence providers"""
    async def save_session(self, session: Session) -> None: ...
    async def load_session(self, session_id: uuid.UUID) -> Optional[Session]: ...

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
        self.sessions: Dict[uuid.UUID, Session] = {}

    async def initialize_session(self, session: Session) -> Session:
        """Initialize a state machine for a session"""
        if session.id in self.sessions:
            return self.sessions[session.id]

        if not session.template:
            raise ValueError("Session must have a template")

        # Extract states and transitions
        states, transitions = self._build_state_machine_config(session.template)

        # Initialize workflow data
        self._initialize_workflow_data(session)

        # Create state machine
        machine = AsyncGraphMachine(
            model=session,
            states=states,
            transitions=transitions,
            initial=session.current_state or 'start',
            send_event=True,
            auto_transitions=False,
            model_attribute='current_state',
            after_state_change=self._after_state_change,
        )

        session.machine = machine

        if session.id is not None:
            self.sessions[session.id] = session

        return session

    def _build_state_machine_config(self, template: SessionTemplate):
        """Build states and transitions config for state machine"""
        states = ['start', 'end']
        transitions = []

        enabled_steps = [step for step in template.steps if step.enabled]

        for i, step in enumerate(enabled_steps):
            # Add state
            state_name = f'step_{i}'
            states.insert(len(states) - 1, state_name)

            # Add transition to this state
            source = 'start' if i == 0 else f'step_{i-1}'

            transition = {
                'trigger': f'run_{state_name}',
                'source': source,
                'dest': state_name,
                'before': self._execute_step,
                'conditions': self._can_execute_step
            }
            transitions.append(transition)

            # Add final transition if this is the last step
            if i == len(enabled_steps) - 1:
                transitions.append({
                    'trigger': 'finalize',
                    'source': state_name,
                    'dest': 'end',
                    'before': self._finalize_workflow
                })

        return states, transitions

    def _initialize_workflow_data(self, session: Session) -> None:
        """Initialize workflow data structure"""
        if not session.workflow_data:
            session.workflow_data = {}

        session.workflow_data.update({
            'current_step_index': session.workflow_data.get('current_step_index', 0),
            'step_results': session.workflow_data.get('step_results', {}),
            'variables': session.workflow_data.get('variables', {}),
            'errors': session.workflow_data.get('errors', []),
            'messages': session.workflow_data.get('messages', [])
        })

    async def _after_state_change(self, event):
        """Handle state change events"""
        session = event.model
        await self.persistence.save_session(session)

    async def _can_execute_step(self, event):
        """Check if a step can be executed"""
        session = event.model
        next_step = await self.get_current_step(session)

        if not next_step:
            return False

        handler = self.handlers.get(next_step.type)
        if not handler:
            return False

        return await handler.can_handle(session, next_step)

    async def _execute_step(self, event):
        """Execute the current step"""
        session = event.model
        next_step = await self.get_current_step(session)

        if not next_step:
            return

        handler = self.handlers.get(next_step.type)
        if not handler:
            session.workflow_data['errors'].append(f"No handler for step type: {next_step.type}")
            return

        try:
            result = await handler.handle(session, next_step)

            # Update workflow data
            session.workflow_data['current_step_index'] += 1
            session.workflow_data['step_results'][next_step.name] = {
                'completed': True,
                **result
            }

        except Exception as e:
            session.workflow_data['errors'].append(str(e))
            session.status = 'error'

    async def _finalize_workflow(self, event):
        """Finalize the workflow"""
        session = event.model
        session.status = 'completed'

    async def get_current_step(self, session: Session) -> Optional[Step]:
        """Get the current step to execute"""
        if not session.template:
            return None

        enabled_steps = [step for step in session.template.steps if step.enabled]
        current_index = session.workflow_data.get('current_step_index', 0)

        if current_index < len(enabled_steps):
            return enabled_steps[current_index]
        return None

    async def execute_next_step(self, session: Session) -> WorkflowTransitionResult:
        """Execute the next step in the workflow"""
        next_step = await self.get_current_step(session)
        if not next_step:
            # No more steps to execute
            result = WorkflowTransitionResult(
                success=False,
                state=session.current_state,
                message="No more steps to execute"
            )
            # Ensure session is saved even when there are no more steps
            await self.persistence.save_session(session)
            return result

        # Find the trigger for this step
        trigger_name = f'run_step_{session.workflow_data.get("current_step_index", 0)}'

        # Check if the trigger exists
        if hasattr(session, trigger_name):
            trigger_method = getattr(session, trigger_name)

            try:
                await trigger_method()

                # Check if we're waiting for input
                if session.status == 'waiting_for_input':
                    missing_vars = session.workflow_data.get('missing_variables', [])
                    await self.persistence.save_session(session)
                    return WorkflowTransitionResult(
                        success=False,
                        state=session.current_state,
                        waiting_for_input=True,
                        required_variables=missing_vars,
                        message=f"Waiting for input: {missing_vars}"
                    )


                return WorkflowTransitionResult(
                    success=True,
                    state=session.current_state,
                    message="Step executed successfully"
                )

            except Exception as e:
                # Save error state to workflow data
                session.workflow_data['errors'].append(str(e))
                session.status = 'error'
                # Ensure session is saved when an exception occurs
                await self.persistence.save_session(session)
                return WorkflowTransitionResult(
                    success=False,
                    state=session.current_state,
                    message=f"Error executing step: {str(e)}"
                )

        # Trigger not found
        result = WorkflowTransitionResult(
            success=False,
            state=session.current_state,
            message=f"Trigger {trigger_name} not found"
        )
        # Ensure session is saved even when trigger is not found
        await self.persistence.save_session(session)
        return result
