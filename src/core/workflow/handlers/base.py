import json
import uuid
from typing import Any, Dict, Optional, Type, List
from abc import ABC, abstractmethod
from pydantic import BaseModel

from src.core.config_types import Step
from src.core.models import Dialog, Message, MessageStatus
from src.core.workflow.step_result import StepResult


class BaseStepHandler(ABC):
    """Base class for all step handlers"""

    @abstractmethod
    async def can_handle(self, dialog: Dialog, step: Step) -> bool:
        """
        Check if the step can be handled by this handler.
        
        Args:
            dialog: The dialog containing the step
            step: The step to check
            
        Returns:
            True if the step can be handled, False otherwise
        """
        pass

    @abstractmethod
    async def handle(self, dialog: Dialog, step: Step) -> StepResult:
        """
        Handle the step execution.
        
        Args:
            dialog: The dialog containing the step
            step: The step to handle
            
        Returns:
            A StepResult containing the result of the step execution
        """
        pass
    
    def validate_step_type(self, step: Step, expected_type: type) -> None:
        """
        Validate that the step is of the expected type.
        
        Args:
            step: The step to validate
            expected_type: The expected type of the step
            
        Raises:
            TypeError: If the step is not of the expected type
        """
        if not isinstance(step, expected_type):
            raise TypeError(f"Expected {expected_type.__name__} but got {type(step).__name__}")
    
    def get_variables(self, dialog: Dialog, step: Step) -> Dict[str, Any]:
        """
        Get all variables for the step, applying precedence rules.
        
        Precedence (lowest to highest):
        1. Dialog workflow variables
        2. Step template_args (if available)
        
        Args:
            dialog: The dialog containing the variables
            step: The step that may contain template_args
            
        Returns:
            A dictionary of all variables
        """
        # Start with dialog workflow variables
        variables = dialog.workflow_data.variables.copy()
        
        # Add template_args if available (overriding any existing variables)
        if hasattr(step, 'template_args') and step.template_args:
            variables.update(step.template_args)
            
        return variables
    
    def configure_response_schema(self, schema_class: Type[BaseModel]) -> Dict[str, Any]:
        """
        Configure a response schema from a Pydantic model.
        
        Args:
            schema_class: The Pydantic model class to use for the schema
            
        Returns:
            A dictionary containing the JSON schema
        """
        schema = schema_class.model_json_schema()
        return {
            "response_format": {
                "type": "json_object",
                "schema": schema
            }
        }
    
    def create_message(self, dialog: Dialog, role: str, text: str, model: Optional[str] = None, 
                      status: MessageStatus = MessageStatus.CREATED) -> Message:
        """
        Create a new message for the dialog.
        
        Args:
            dialog: The dialog to add the message to
            role: The role of the message (user, assistant, system)
            text: The text content of the message
            model: The model used (required for assistant messages)
            status: The status of the message
            
        Returns:
            The created message
        """
        message = Message(
            id=uuid.uuid4(),
            dialog_id=dialog.id,
            role=role,
            model=model if role == 'assistant' else None,
            text=text,
            status=status
        )
        
        # Add the message to the dialog
        dialog.messages.append(message)
        
        return message
    
    def create_messages_from_list(self, dialog: Dialog, messages: List[Dict[str, str]], 
                                 model: Optional[str] = None) -> List[Message]:
        """
        Create multiple messages from a list of message dictionaries.
        
        Args:
            dialog: The dialog to add the messages to
            messages: List of message dictionaries with 'role' and 'content' keys
            model: The model to use for assistant messages
            
        Returns:
            List of created messages
        """
        created_messages = []
        
        for msg_data in messages:
            message = self.create_message(
                dialog=dialog,
                role=msg_data['role'],
                text=msg_data['content'],
                model=model if msg_data['role'] == 'assistant' else None
            )
            created_messages.append(message)
            
        return created_messages
    
    def update_message_status(self, message: Message, status: MessageStatus) -> None:
        """
        Update the status of a message.
        
        Args:
            message: The message to update
            status: The new status
        """
        message.status = status
