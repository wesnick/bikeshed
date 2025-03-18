from typing import Any, Dict, List, Optional, Union, Callable, Awaitable
import uuid

from transitions.core import EventData
from transitions.extensions.asyncio import AsyncMachine

from src.dependencies import get_db
from src.models.models import Session, Message
from src.core.config_types import Step, MessageStep, PromptStep, UserInputStep, InvokeStep
from src.repository.session import SessionRepository
from src.service.logging import logger

class WorkflowService:
    """Service for managing workflow state machines for sessions"""
    
    def __init__(self, session_repo: Optional[SessionRepository] = None):
        self.sessions: Dict[uuid.UUID, Session] = {}
        self.session_repo = session_repo or SessionRepository()
        
        # Register this instance in a global registry so transitions can find it
        if not hasattr(WorkflowService, '_instances'):
            WorkflowService._instances = {}
        self._instance_id = str(uuid.uuid4())
        WorkflowService._instances[self._instance_id] = self
        
    @classmethod
    def get_instance(cls, instance_id):
        """Get a workflow service instance by ID"""
        return cls._instances.get(instance_id)
        
    async def initialize_session(self, session: Session) -> Session:
        """Initialize a state machine for a session based on its template"""
        if not session.template:
            raise ValueError("Session must have a template to initialize workflow")
        
        # Extract step names for states
        steps = session.template.steps
        states = ['start'] + [f'step{i}' for i, step in enumerate(steps) if step.enabled] + ['end']
        
        # Store the workflow service instance ID in the session for callback resolution
        if not session.workflow_data:
            session.workflow_data = {}
        session.workflow_data['workflow_service_id'] = self._instance_id
        
        # Create transitions between states
        transitions = []
        for i, step in enumerate([s for s in steps if s.enabled]):
            source = 'start' if i == 0 else f'run_step{i-1}'
            dest = 'end' if i == len([s for s in steps if s.enabled]) - 1 else f'step{i+1}'
            
            # Create callback paths that will be resolved by our custom callback resolver
            transitions.append({
                'trigger': f'run_step{i}',
                'source': source,
                'dest': dest,
                'before': f'src.service.workflow._before_{step.type}',
                'after': f'src.service.workflow._after_{step.type}',
                'conditions': f'src.service.workflow._check_step_enabled'
            })
        
        # Initialize workflow data if not fully present
        if not session.workflow_data:
            session.workflow_data = {}
            
        # Ensure all required workflow data fields exist
        session.workflow_data.update({
            'current_step_index': session.workflow_data.get('current_step_index', 0),
            'step_results': session.workflow_data.get('step_results', {}),
            'variables': session.workflow_data.get('variables', {}),
            'errors': session.workflow_data.get('errors', [])
        })
        
        # Create state machine with custom callback resolver
        machine = AsyncMachine(
            model=session,
            states=states,
            transitions=transitions,
            initial='start',
            send_event=True,
            auto_transitions=False,
            model_attribute='status',
            after_state_change=f'src.service.workflow._persist_state'
        )
        
        # Override the resolve_callable method to handle our custom callback format
        original_resolve = machine.resolve_callable

        def custom_resolve_callable(func, event_data):
            if isinstance(func, str) and func.startswith('workflow_service:'):
                # Extract the method name from our custom format
                method_name = func.split(':', 1)[1]
                # Get the workflow service instance from the session's workflow data
                service_id = event_data.model.workflow_data.get('workflow_service_id')
                service = WorkflowService.get_instance(service_id)
                if service and hasattr(service, method_name):
                    return getattr(service, method_name)
            # Fall back to the original resolver for other cases
            return original_resolve(func, event_data)

        machine.resolve_callable = custom_resolve_callable
        
        # Store the machine on the session
        session.machine = machine

        # Store session in our registry
        self.sessions[session.id] = session
        return session
    
    async def get_next_step(self, session: Session) -> Optional[Step]:
        """Get the next step to execute in the workflow"""
        if not session.template:
            return None
            
        enabled_steps = [step for step in session.template.steps if step.enabled]
        current_index = session.workflow_data.get('current_step_index', 0)
        
        if current_index < len(enabled_steps):
            return enabled_steps[current_index]
        return None
    
    async def execute_next_step(self, session: Session) -> bool:
        """Execute the next step in the workflow"""
        next_step = await self.get_next_step(session)
        if not next_step:
            return False
            
        # Find the trigger for this step
        step_index = session.workflow_data.get('current_step_index', 0)
        trigger = f'run_step{step_index}'
        
        # Check if the trigger exists
        if hasattr(session, trigger):
            trigger_method = getattr(session, trigger)
            logger.info(f"Trigger Before: session: {session.status} workflows: {session.machine.get_model_state(session).name} trigger: {trigger}")
            await trigger_method()
            logger.info(
                f"Trigger Info: session: {session.status} workflow: {session.machine.get_model_state(session).name} trigger: {trigger}")

            return True
        else:
            logger.error(f"Trigger {trigger} not found for session {session.id}")
            return False

    async def _check_step_enabled(self, event: Dict[str, Any]) -> bool:
        """Check if the current step is enabled"""
        session = event.model
        next_step = await self.get_next_step(session)
        return next_step and next_step.enabled

    # Step type handlers
    async def _before_message(self, event: Dict[str, Any]) -> None:
        """Prepare for message step execution"""
        session = event.model
        next_step = await self.get_next_step(session)
        if not isinstance(next_step, MessageStep):
            logger.error(f"Expected MessageStep but got {type(next_step)}")
            return

        logger.info(f"Preparing message step: {next_step.name}")
        session.status = 'running'

    async def _after_message(self, event: Dict[str, Any]) -> None:
        """Handle message step completion"""
        session = event.model
        step = await self.get_next_step(session)
        if not isinstance(step, MessageStep):
            return

        # Create a message in the database
        message = Message(
            session_id=session.id,
            role=step.role,
            text=step.content or "",
            status='delivered'
        )

        # Add to session's messages (this would be persisted by the caller)
        if not hasattr(session, '_temp_messages') or session._temp_messages is None:
            session._temp_messages = []
        session._temp_messages.append(message)

        # Update workflow data
        session.workflow_data['current_step_index'] += 1
        session.workflow_data['step_results'][step.name] = {
            'completed': True,
            'message_id': str(message.id)
        }

        logger.info(f"Completed message step: {step.name}")

    async def _before_prompt(self, event: Dict[str, Any]) -> None:
        """Prepare for prompt step execution"""
        session = event.model
        next_step = await self.get_next_step(session)
        if not isinstance(next_step, PromptStep):
            return

        logger.info(f"Preparing prompt step: {next_step.name}")
        session.status = 'running'

    async def _after_prompt(self, event: Dict[str, Any]) -> None:
        """Handle prompt step completion"""
        session = event.model
        step = await self.get_next_step(session)
        if not isinstance(step, PromptStep):
            return

        # This would call the LLM service in a real implementation
        # For now, just create a placeholder response
        response = f"LLM response for prompt: {step.content or step.template}"

        # Create messages for the prompt and response
        user_message = Message(
            session_id=session.id,
            role="user",
            text=step.content or "",
            status='delivered'
        )

        assistant_message = Message(
            session_id=session.id,
            role="assistant",
            text=response,
            status='delivered',
            parent_id=user_message.id
        )

        # Add to session's messages
        if not hasattr(session, '_temp_messages') or session._temp_messages is None:
            session._temp_messages = []
        session._temp_messages.extend([user_message, assistant_message])

        # Update workflow data
        session.workflow_data['current_step_index'] += 1
        session.workflow_data['step_results'][step.name] = {
            'completed': True,
            'prompt_message_id': str(user_message.id),
            'response_message_id': str(assistant_message.id),
            'response': response
        }

        logger.info(f"Completed prompt step: {step.name}")

    async def _before_user_input(self, event: Dict[str, Any]) -> None:
        """Prepare for user input step execution"""
        session = event.model
        next_step = await self.get_next_step(session)
        if not isinstance(next_step, UserInputStep):
            return

        logger.info(f"Preparing user input step: {next_step.name}")
        session.status = 'waiting_for_input'

    async def _after_user_input(self, event: Dict[str, Any]) -> None:
        """Handle user input step completion"""
        session = event.model
        step = await self.get_next_step(session)
        if not isinstance(step, UserInputStep):
            return

        # In a real implementation, this would wait for user input
        # For now, just create a placeholder
        user_input = session.workflow_data.get('user_input', "Sample user input")

        # Create a message for the user input
        message = Message(
            session_id=session.id,
            role="user",
            text=user_input,
            status='delivered'
        )

        # Add to session's messages
        if not hasattr(session, '_temp_messages') or session._temp_messages is None:
            session._temp_messages = []
        session._temp_messages.append(message)

        # Update workflow data
        session.workflow_data['current_step_index'] += 1
        session.workflow_data['step_results'][step.name] = {
            'completed': True,
            'message_id': str(message.id),
            'input': user_input
        }

        logger.info(f"Completed user input step: {step.name}")

    async def _before_invoke(self, event: Dict[str, Any]) -> None:
        """Prepare for invoke step execution"""
        session = event.model
        next_step = await self.get_next_step(session)
        if not isinstance(next_step, InvokeStep):
            return

        logger.info(f"Preparing invoke step: {next_step.name}")
        session.status = 'running'

    async def _after_invoke(self, event: Dict[str, Any]) -> None:
        """Handle invoke step completion"""
        session = event.model
        step = await self.get_next_step(session)
        if not isinstance(step, InvokeStep):
            return

        # In a real implementation, this would call the function
        # For now, just create a placeholder result
        result = f"Result of invoking {step.callable}"

        # Update workflow data
        session.workflow_data['current_step_index'] += 1
        session.workflow_data['step_results'][step.name] = {
            'completed': True,
            'result': result
        }

        logger.info(f"Completed invoke step: {step.name}")

    async def provide_user_input(self, session: Session, user_input: str) -> bool:
        """Provide user input for a waiting user_input step"""
        if session.status != 'waiting_for_input':
            return False

        # Store the input in workflow data
        session.workflow_data['user_input'] = user_input

        # Execute the step now that we have input
        return await self.execute_next_step(session)

    async def _persist_state(self, event: EventData):

        """Persist the state of the session to the database"""
        session = event.model
        logger.info(f"Persisting state for session: {session.id}")

        async for db in get_db():
            # Update session data
            await self.session_repo.update(db, session.id, {
                'status': session.status,
                'current_state': session.machine.get_model_state(session).name,
                'workflow_data': session.workflow_data
            })

            # Save any temporary messages
            if hasattr(session, '_temp_messages') and session._temp_messages:
                for msg in session._temp_messages:
                    # Ensure message has session_id (should be set when created)
                    if not msg.session_id:
                        msg.session_id = session.id
                    db.add(msg)
                session._temp_messages = []  # Clear the temporary messages

            await db.commit()
