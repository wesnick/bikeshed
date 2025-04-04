from typing import Dict

from src.core.workflow.handlers.base import BaseStepHandler
from src.core.workflow.handlers.message import MessageStepHandler
from src.core.workflow.handlers.prompt import PromptStepHandler
from src.core.workflow.handlers.user_input import UserInputStepHandler
from src.core.workflow.handlers.invoke import InvokeStepHandler
from src.core.config_types import Step, MessageStep, PromptStep, UserInputStep, InvokeStep


class HandlerFactory:
    """Factory for creating step handlers"""

    def __init__(self, registry, completion_service):
        self.registry = registry
        self.completion_service = completion_service
        self._handlers = None

    async def get_handlers(self) -> Dict[str, BaseStepHandler]:
        """Get all handlers"""

        if self._handlers is None:
            self._handlers = {
                'message': MessageStepHandler(self.registry, self.completion_service),
                'prompt': PromptStepHandler(self.registry, self.completion_service),
                'user_input': UserInputStepHandler(self.registry, self.completion_service),
                'invoke': InvokeStepHandler(self.registry, self.completion_service)
            }
        return self._handlers

    async def get_handler_for_step(self, step: Step) -> BaseStepHandler:
        """Get the appropriate handler for a step"""
        handlers = await self.get_handlers()

        if isinstance(step, MessageStep):
            return handlers['message']
        elif isinstance(step, PromptStep):
            return handlers['prompt']
        elif isinstance(step, UserInputStep):
            return handlers['user_input']
        elif isinstance(step, InvokeStep):
            return handlers['invoke']
        else:
            raise ValueError(f"No handler available for step type: {type(step)}")
