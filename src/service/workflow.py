from typing import Any, Dict, List, Optional, Union, Callable, Awaitable
import uuid

from transitions.core import EventData
from transitions.extensions.asyncio import AsyncMachine

from src.dependencies import get_db
from src.models.models import Session, Message
from src.core.config_types import Step, MessageStep, PromptStep, UserInputStep, InvokeStep
from src.repository import session_repository
from src.service.logging import logger

async def persist_workflow(event: EventData):
    """Persist the state of the session to the database"""
    session: Session = event.model
    logger.info(f"Persisting state: {session.status} machine_state: {session.machine.get_model_state(session).name} current_state: {session.current_state} for session: {session.id} event: {event.event.name}")

    async for db in get_db():
        try:
            # First, ensure the session exists in the database
            db_session = await session_repository.get_by_id(db, session.id)
            if not db_session:
                # Create the session in the database
                db.add(session)
                await db.flush()  # This assigns an ID if needed and makes it available in the session
            
            # Update session data
            await session_repository.update(db, session.id, {
                'status': session.status,
                'current_state': session.machine.get_model_state(session).name,
                'workflow_data': session.workflow_data
            })

            # Save any temporary messages
            if hasattr(session, '_temp_messages') and session._temp_messages:
                for msg in session._temp_messages:
                    # Ensure message has session_id and ID
                    if not msg.session_id:
                        msg.session_id = session.id
                    if not msg.id:
                        msg.id = uuid.uuid4()
                    db.add(msg)
                session._temp_messages = []  # Clear the temporary messages

            await db.commit()
        except Exception as e:
            logger.error(f"Error persisting workflow: {e}")
            await db.rollback()
            raise  # Re-raise the exception to properly handle errors

async def on_message(event: EventData) -> None:
    """Prepare for message step execution"""
    session = event.model
    next_step = await WorkflowService.get_next_step(session)
    if not isinstance(next_step, MessageStep):
        logger.error(f"Expected MessageStep but got {type(next_step)}")
        return

    logger.info(f"Preparing message step: {next_step.name}")
    session.status = 'running'

    # Create a message in the database
    message = Message(
        id=uuid.uuid4(),  # Ensure ID is set
        session_id=session.id,
        role=next_step.role,
        text=next_step.content or "",
        status='delivered'
    )

    # Add to session's messages (this would be persisted by the caller)
    if not hasattr(session, '_temp_messages') or session._temp_messages is None:
        session._temp_messages = []
    session._temp_messages = [message]  # Replace instead of append

    # Update workflow data
    session.workflow_data['current_step_index'] += 1
    session.workflow_data['step_results'][next_step.name] = {
        'completed': True,
        'message_id': str(message.id)
    }

    logger.info(f"Completed message step: {next_step.name}")

async def on_prompt(event: EventData) -> None:
    """Handle prompt step completion"""
    session: Session = event.model
    next_step = await WorkflowService.get_next_step(session)

    if not isinstance(next_step, PromptStep):
        return

    logger.info(f"Preparing prompt step: {next_step.name}")
    session.status = 'running'

    # This would call the LLM service in a real implementation
    # For now, just create a placeholder response
    response = f"LLM response for prompt: {next_step.content or next_step.template}"

    # Create messages for the prompt and response
    user_message = Message(
        id=uuid.uuid4(),  # Ensure ID is set
        session_id=session.id,
        role="user",
        text=next_step.content or "",
        status='delivered'
    )

    assistant_message = Message(
        id=uuid.uuid4(),  # Ensure ID is set
        session_id=session.id,
        role="assistant",
        text=response,
        status='delivered',
        parent_id=user_message.id
    )

    # Add to session's messages
    if not hasattr(session, '_temp_messages') or session._temp_messages is None:
        session._temp_messages = []
    session._temp_messages = [user_message, assistant_message]  # Replace instead of extend

    # Update workflow data
    session.workflow_data['current_step_index'] += 1
    session.workflow_data['step_results'][next_step.name] = {
        'completed': True,
        'prompt_message_id': str(user_message.id),
        'response_message_id': str(assistant_message.id),
        'response': response
    }

    logger.info(f"Completed prompt step: {next_step.name}")

async def on_user_input(event: EventData) -> None:
    """Handle user input step completion"""
    session = event.model
    next_step = await WorkflowService.get_next_step(session)
    if not isinstance(next_step, UserInputStep):
        return

    logger.info(f"Preparing user input step: {next_step.name}")
    session.status = 'waiting_for_input'

    # In a real implementation, this would wait for user input
    # For now, just create a placeholder
    user_input = session.workflow_data.get('user_input', "Sample user input")

    # Create a message for the user input
    message = Message(
        id=uuid.uuid4(),  # Ensure ID is set
        session_id=session.id,
        role="user",
        text=user_input,
        status='delivered'
    )

    # Add to session's messages
    if not hasattr(session, '_temp_messages') or session._temp_messages is None:
        session._temp_messages = []
    session._temp_messages = [message]  # Replace instead of append

    # Update workflow data
    session.workflow_data['current_step_index'] += 1
    session.workflow_data['step_results'][next_step.name] = {
        'completed': True,
        'message_id': str(message.id),
        'input': user_input
    }

    logger.info(f"Completed user input step: {next_step.name}")

async def on_invoke(event: EventData) -> None:
    """Handle invoke step completion"""
    session = event.model
    next_step = await WorkflowService.get_next_step(session)
    if not isinstance(next_step, InvokeStep):
        return

    logger.info(f"Preparing invoke step: {next_step.name}")
    session.status = 'running'

    # In a real implementation, this would call the function
    # For now, just create a placeholder result
    result = f"Result of invoking {next_step.callable}"

    # Update workflow data
    session.workflow_data['current_step_index'] += 1
    session.workflow_data['step_results'][next_step.name] = {
        'completed': True,
        'result': result
    }

    logger.info(f"Completed invoke step: {next_step.name}")


class WorkflowService:
    """Service for managing workflow state machines for sessions"""
    
    def __init__(self):
        self.sessions: Dict[uuid.UUID, Session] = {}  # Keep track of initialized sessions
        
    async def initialize_session(self, session: Session) -> Session:
        """Initialize a state machine for a session based on its template"""
        if not session.template:
            raise ValueError("Session must have a template to initialize workflow")
        
        # Extract step names for states, ensuring the index reflects disabled elements
        steps = session.template.steps
        states = ['start']

        # Create transitions between states, ensuring the index reflects disabled elements
        transitions = []
        enabled_steps_count = 0
        for i, step in enumerate(steps):
            if step.enabled:
                states.append(f'step{i}')
                source = 'start' if enabled_steps_count == 0 else f'step{i-1}'
                dest = 'end' if enabled_steps_count == len([s for s in steps if s.enabled]) - 1 else f'step{i}'
                transitions.append({
                    'trigger': f'run_step{i}',
                    'source': source,
                    'dest': dest,
                    'before': f'src.service.workflow.on_{step.type}'
                })
                enabled_steps_count += 1
        states.append('end')
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
            model_attribute='current_state',
            after_state_change=f'src.service.workflow.persist_workflow',
        )
      
        
        # Store the machine on the session
        session.machine = machine

        # Store session in our registry
        self.sessions[session.id] = session
        return session
    
    @staticmethod
    async def get_next_step(session: Session) -> Optional[Step]:
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

    async def provide_user_input(self, session: Session, user_input: str) -> bool:
        """Provide user input for a waiting user_input step"""
        if session.status != 'waiting_for_input':
            return False

        # Store the input in workflow data
        session.workflow_data['user_input'] = user_input

        # Execute the step now that we have input
        return await self.execute_next_step(session)
