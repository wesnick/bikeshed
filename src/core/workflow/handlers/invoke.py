from typing import Any, Dict, Callable
import importlib
import inspect

from src.core.workflow.handlers import BaseStepHandler
from src.core.workflow.engine import StepResult
from src.core.config_types import InvokeStep, Step
from src.core.models import Dialog, DialogStatus


class InvokeStepHandler(BaseStepHandler):
    """Handler for invoke steps"""

    async def get_step_requirements(self, dialog: Dialog, step: Step) -> StepRequirements:
        """Get the requirements for an invoke step"""
        requirements = StepRequirements()
        
        if not isinstance(step, InvokeStep):
            return requirements
            
        # Add required arguments
        if step.args:
            for arg_name in step.args:
                requirements.add_required_variable(
                    arg_name,
                    f"Input for function argument: {arg_name}",
                    True
                )
                
        # Add standard output
        requirements.add_provided_output(
            "result",
            f"Output from function call: {step.callable}",
            step.name
        )
            
        return requirements

    async def handle(self, dialog: Dialog, step: Step) -> StepResult:
        """Handle an invoke step"""
        await self.validate_step_type(step, InvokeStep)

        # Set status to running
        dialog.status = DialogStatus.RUNNING

        # Get the callable function
        func = await self._get_callable(step.callable)

        # Prepare arguments
        args = await self.prepare_arguments(dialog, step)

        # Add dialog to kwargs if the function accepts it
        sig = inspect.signature(func)
        valid_params = sig.parameters.keys()

        filtered_args = {k: v for k, v in args.items() if k in valid_params}

        # Execute the function
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(**filtered_args)
            else:
                result = func(**filtered_args)

            # Return step result
            return StepResult.success_result(
                state=dialog.current_state,
                data=result,
            )
        except Exception as e:
            # Handle error
            error_message = f"Error invoking {step.callable}: {str(e)}"
            dialog.workflow_data.errors.append(error_message)

            return StepResult.failure_result(
                state=dialog.current_state,
                message=error_message
            )

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
