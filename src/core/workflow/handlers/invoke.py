from typing import Any, Dict, Callable, Awaitable
import importlib
import inspect
import uuid

from src.core.workflow.engine import StepHandler
from src.core.config_types import InvokeStep, Step
from src.models.models import Session, Message


class InvokeStepHandler(StepHandler):
    """Handler for invoke steps"""

    async def can_handle(self, session: Session, step: Step) -> bool:
        """Check if the step can be handled"""
        return isinstance(step, InvokeStep)

    async def handle(self, session: Session, step: Step) -> Dict[str, Any]:
        """Handle an invoke step"""
        if not isinstance(step, InvokeStep):
            raise TypeError(f"Expected InvokeStep but got {type(step)}")

        # Set status to running
        session.status = 'running'

        # Get the callable function
        func = await self._get_callable(step.callable)
        
        # Prepare arguments
        args = step.args or []
        kwargs = step.kwargs or {}
        
        # Add session to kwargs if the function accepts it
        sig = inspect.signature(func)
        if 'session' in sig.parameters:
            kwargs['session'] = session
            
        # Execute the function
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                
            # Return step result
            return {
                'result': result,
                'completed': True
            }
        except Exception as e:
            # Handle error
            error_message = f"Error invoking {step.callable}: {str(e)}"
            session.workflow_data.errors.append(error_message)
            
            return {
                'error': error_message,
                'completed': False
            }
    
    async def _get_callable(self, callable_path: str) -> Callable[..., Any]:
        """Get a callable function from its import path"""
        try:
            # Split the path into module and function
            module_path, func_name = callable_path.rsplit('.', 1)
            
            # Import the module
            module = importlib.import_module(module_path)
            
            # Get the function
            func = getattr(module, func_name)
            
            return func
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Could not import callable {callable_path}: {str(e)}")
