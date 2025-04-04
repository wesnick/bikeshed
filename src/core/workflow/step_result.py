from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class StepResult:
    """
    Unified result class for workflow steps and transitions.
    Provides a consistent interface and context sharing between steps.
    """
    success: bool
    state: str
    message: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    waiting_for_input: bool = False
    required_variables: Optional[List[str]] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success_result(cls, state: str, message: Optional[str] = None, **kwargs) -> 'StepResult':
        """Factory method for creating a successful result"""
        return cls(
            success=True,
            state=state,
            message=message or "Step executed successfully",
            **kwargs
        )
    
    @classmethod
    def failure_result(cls, state: str, message: Optional[str] = None, **kwargs) -> 'StepResult':
        """Factory method for creating a failure result"""
        return cls(
            success=False,
            state=state,
            message=message or "Step execution failed",
            **kwargs
        )
    
    @classmethod
    def waiting_result(cls, state: str, required_variables: List[str], **kwargs) -> 'StepResult':
        """Factory method for creating a waiting for input result"""
        return cls(
            success=False,
            state=state,
            waiting_for_input=True,
            required_variables=required_variables,
            message=f"Waiting for input: {required_variables}",
            **kwargs
        )
    
    def update_context(self, **kwargs) -> 'StepResult':
        """Update the context with new values"""
        self.context.update(kwargs)
        return self
    
    def merge(self, other: 'StepResult') -> 'StepResult':
        """Merge another result into this one"""
        # Merge data
        self.data.update(other.data)
        # Merge context
        self.context.update(other.context)
        # Update required variables if waiting for input
        if other.waiting_for_input and other.required_variables:
            self.waiting_for_input = True
            if self.required_variables is None:
                self.required_variables = []
            self.required_variables.extend(other.required_variables)
        
        # Update success status (if either fails, the result fails)
        if not other.success:
            self.success = False
            
        return self
