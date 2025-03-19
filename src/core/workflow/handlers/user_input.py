from typing import Any, Dict
import uuid

from src.core.workflow.engine import StepHandler
from src.core.config_types import UserInputStep, Step
from src.models.models import Session, Message

class UserInputStepHandler(StepHandler):
    """Handler for user_input steps"""

    async def can_handle(self, session: Session, step: Step) -> bool:
        """Check if the step can be handled"""
        if not isinstance(step, UserInputStep):
            return False
            
        # Check if user_input exists in workflow_data
        return 'user_input' in session.workflow_data and session.workflow_data['user_input'] is not None

    async def handle(self, session: Session, step: Step) -> Dict[str, Any]:
        """Handle a user_input step"""
        if not isinstance(step, UserInputStep):
            raise TypeError(f"Expected UserInputStep but got {type(step)}")
            
        # Get the user input from workflow data
        user_input = session.workflow_data.get('user_input')
        
        if not user_input:
            # If no user input is available, set status to waiting and exit
            session.status = 'waiting_for_input'
            return {'completed': False, 'waiting_for_input': True}
        
        # Create a message for the user input
        message = Message(
            id=uuid.uuid4(),
            session_id=session.id,
            role="user",
            text=user_input,
            status='delivered'
        )

        # Add to session's messages
        if not hasattr(session, '_temp_messages'):
            session._temp_messages = []
        session._temp_messages.append(message)

        # Clear the user_input after processing
        session.workflow_data.pop('user_input', None)
        
        # Update status to running
        session.status = 'running'

        # Return step result
        return {
            'message_id': str(message.id),
            'input': user_input,
            'completed': True
        }
