from typing import Any, Dict, List, Optional, Union, Callable, Awaitable
import uuid
from transitions.extensions.asyncio import AsyncMachine

from src.models.models import Session, Message
from src.core.config_types import Step, MessageStep, PromptStep, UserInputStep, InvokeStep
from src.service.logging import logger

class WorkflowService:
    """Service for managing workflow state machines for sessions"""
    
    def __init__(self):
        self.sessions: Dict[uuid.UUID, Session] = {}
        
    async def initialize_session(self, session: Session) -> Session:
        """Initialize a state machine for a session based on its template"""
        if not session.template:
            raise ValueError("Session must have a template to initialize workflow")
        
        # Extract step names for states
        steps = session.template.steps
        states = ['start'] + [step.name for step in steps if step.enabled] + ['end']
        
        # Create transitions between states
        transitions = []
        for i, step in enumerate([s for s in steps if s.enabled]):
            source = 'start' if i == 0 else steps[i-1].name
            dest = 'end' if i == len([s for s in steps if s.enabled]) - 1 else steps[i+1].name
            
            transitions.append({
                'trigger': f'execute_{step.name}',
                'source': source,
                'dest': dest,
                'before': f'_before_{step.type}',
                'after': f'_after_{step.type}',
                'conditions': '_check_step_enabled'
            })
        
        # Initialize workflow data if not present
        if not session.workflow_data:
            session.workflow_data = {
                'current_step_index': 0,
                'step_results': {},
                'variables': {},
                'errors': []
            }
        
        # Create state machine
        machine = AsyncMachine(
            model=session,
            states=states,
            transitions=transitions,
            initial='start',
            send_event=True,
            auto_transitions=False
        )
        
        # Add callbacks for different step types
        session.machine = machine
        
        # Register step type handlers
        machine.add_model_method('_before_message', self._before_message)
        machine.add_model_method('_after_message', self._after_message)
        machine.add_model_method('_before_prompt', self._before_prompt)
        machine.add_model_method('_after_prompt', self._after_prompt)
        machine.add_model_method('_before_user_input', self._before_user_input)
        machine.add_model_method('_after_user_input', self._after_user_input)
        machine.add_model_method('_before_invoke', self._before_invoke)
        machine.add_model_method('_after_invoke', self._after_invoke)
        machine.add_model_method('_check_step_enabled', self._check_step_enabled)
        
        # Store session
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
        trigger = f'execute_{next_step.name}'
        
        # Check if the trigger exists
        if hasattr(session, trigger):
            trigger_method = getattr(session, trigger)
            await trigger_method()
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
        if not hasattr(session, '_temp_messages'):
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
        if not hasattr(session, '_temp_messages'):
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
        if not hasattr(session, '_temp_messages'):
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

