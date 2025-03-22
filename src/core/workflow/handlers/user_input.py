from typing import Any, Dict
import uuid

from src.core.workflow.engine import StepHandler
from src.core.config_types import UserInputStep, Step
from src.models.models import Session, Message, SessionStatus, MessageStatus


class UserInputStepHandler(StepHandler):
    """Handler for user_input steps"""

    async def can_handle(self, session: Session, step: Step) -> bool:
        """Check if the step can be handled"""
        if not isinstance(step, UserInputStep):
            return False
            
        # Check if user_input exists in workflow_data
        has_user_input = session.workflow_data.user_input is not None

        if not has_user_input:
            # Mark session as waiting for input
            session.status = SessionStatus.WAITING_FOR_INPUT
            session.workflow_data.missing_variables.append('user_input')
            return False

        return True


    async def handle(self, session: Session, step: Step) -> Dict[str, Any]:
        """Handle a user_input step"""
        if not isinstance(step, UserInputStep):
            raise TypeError(f"Expected UserInputStep but got {type(step)}")
            
        # Get the user input from workflow data
        user_input = session.workflow_data.get('user_input')
        
        if not user_input:
            # If no user input is available, set status to waiting and exit
            session.status = SessionStatus.WAITING_FOR_INPUT
            return {'completed': False, 'waiting_for_input': True}
        
        # Create a message for the user input
        message = Message(
            id=uuid.uuid4(),
            session_id=session.id,
            role="user",
            text=user_input,
            status=MessageStatus.CREATED
        )

        session.messages.append(message)

        # Clear the user_input after processing
        session.workflow_data.pop('user_input', None)
        
        # Update status to running
        session.status = SessionStatus.RUNNING

        # Return step result
        return {
            'message_id': str(message.id),
            'input': user_input,
            'completed': True
        }
