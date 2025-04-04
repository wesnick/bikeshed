from typing import Any, Dict, Callable
import importlib
import inspect

from src.core.workflow.handlers.base import StepHandler, StepResult, StepRequirements
from src.core.config_types import InvokeStep, Step
from src.core.models import Dialog, DialogStatus


class InvokeStepHandler(StepHandler):
    """Handler for invoke steps"""

    async def get_step_requirements(self, dialog: Dialog, step: Step) -> StepRequirements:
        """Get the requirements for an invoke step"""
        requirements = StepRequirements()

        if not isinstance(step, InvokeStep):
            return requirements

        # Add required arguments
        func = await self._get_callable(step.callable)
        sig = inspect.signature(func)
        valid_params = sig.parameters

        if valid_params:
            for arg_name, param in valid_params.items():
                data_type = str
                param = sig.parameters[arg_name]
                if param.annotation is not inspect.Parameter.empty:
                    data_type = param.annotation
                requirements.add_required_variable(
                    arg_name,
                    f"Input for function argument: {arg_name}",
                    True,
                    datatype=data_type,
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


async def get_parameter_data_type(func, arg_name: str) -> Any:
    """
    Retrieves the data type of a specified parameter in a function.

    Args:
        func: The function to inspect.
        arg_name: The name of the parameter.

    Returns:
        The data type of the parameter if specified, otherwise None.
    """
    sig = inspect.signature(func)
    if arg_name not in sig.parameters:
        raise ValueError(f"Parameter '{arg_name}' not found in function '{func.__name__}'")

    param = sig.parameters[arg_name]
    if param.annotation is inspect.Parameter.empty:
        return None  # No type hint provided
    else:
        return param.annotation

async def process_function_parameters(step, requirements):
    """
    Processes the parameters of a function, adding required variables to a requirements object.
    """
    func = await self._get_callable(step.callable)
    sig = inspect.signature(func)
    valid_params = sig.parameters

    if valid_params:
        for arg_name, param in valid_params.items():
            data_type = await get_parameter_data_type(func, arg_name)
            requirements.add_required_variable(
                arg_name,
                f"Input for function argument: {arg_name}",
                True,
                data_type=data_type,  # Pass the data type
            )
