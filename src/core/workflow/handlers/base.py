from typing import Any, Dict, Optional, Type, List
from abc import ABC, abstractmethod

from pydantic import BaseModel
from mcp.server.fastmcp.prompts.base import Message as MCPMessage

from src.core.config_types import Step, PromptStep
from src.core.models import Dialog, Message, MessageStatus
from src.core.workflow.engine import StepHandler, StepResult
from src.core.registry import Registry, TemplatePrompt
from src.service.llm import CompletionService
from src.core.workflow.requirements import StepRequirements


class BaseStepHandler(ABC, StepHandler):
    """Base class for all step handlers"""

    def __init__(self, registry: Registry,
                 completion_service: CompletionService):
        """
        Initialize the PromptStepHandler

        Args:
            registry: Registry instance
            completion_service: CompletionService instance
        """
        self.registry = registry
        self.completion_service = completion_service

    @abstractmethod
    async def get_step_requirements(self, dialog: Dialog, step: Step) -> StepRequirements:
        """
        Get the requirements for a step.

        Args:
            dialog: The dialog containing the step
            step: The step to check

        Returns:
            StepRequirements object containing required variables and provided outputs
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

    @staticmethod
    async def validate_step_type(step: Step, expected_type: type) -> None:
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

    @staticmethod
    async def prepare_arguments(dialog: Dialog, step: Step) -> Dict[str, Any]:
        """
        Get all variables for the step, applying precedence rules.

        Precedence (lowest to highest):
        1. Step template_args (if available)
        2. Dialog workflow variables

        Args:
            dialog: The dialog containing the variables
            step: The step that may contain template_args

        Returns:
            A dictionary of all variables
        """
        args = {}

        # Add template_args if available (overriding any existing variables)
        if hasattr(step, 'template_args') and step.template_args:
            args.update(step.template_args)

        # Start with dialog workflow variables
        args = dialog.workflow_data.variables.copy()

        return args

    @staticmethod
    async def prepare_response_schema(schema_class: Type[BaseModel]) -> Dict[str, Any]:
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

    async def prepare_prompt_content(self, dialog: Dialog, step: PromptStep) -> str | list[MCPMessage]:
        """Get the content for a prompt step"""
        if step.content is not None:
            return step.content

        if step.template is not None:
            # Get variables using helper method
            args = await self.prepare_arguments(dialog, step)

            # Get prompt from registry
            prompt = self.registry.get_prompt(step.template)

            if not prompt:
                raise ValueError(f"Prompt template '{step.template}' not found")

            if isinstance(prompt, TemplatePrompt):
                # Add template_content to args
                args['template_raw'] = prompt.template_content
                args['template_path'] = prompt.template_path

            return await prompt.render(args)

        raise ValueError(f"Either content or template must be provided for a {step.type} step")
