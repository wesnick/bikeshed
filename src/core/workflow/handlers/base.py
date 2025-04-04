from typing import Any, Dict, Optional
from abc import ABC, abstractmethod

from src.core.config_types import Step
from src.core.models import Dialog
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
