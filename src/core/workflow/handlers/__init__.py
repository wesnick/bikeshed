from typing import Dict, Type

from src.core.workflow.engine import StepHandler
from src.core.workflow.handlers.message import MessageStepHandler
from src.core.workflow.handlers.prompt import PromptStepHandler
from src.core.workflow.handlers.user_input import UserInputStepHandler
from src.core.workflow.handlers.invoke import InvokeStepHandler
from src.core.config_types import Step, MessageStep, PromptStep, UserInputStep, InvokeStep


class HandlerFactory:
    """Factory for creating step handlers"""
    
    def __init__(self, registry, completion_service):
        self.registry_provider = registry
        self.completion_service = completion_service
        self._handlers = None
        
    async def get_handlers(self) -> Dict[str, StepHandler]:
        """Get all handlers"""

        if self._handlers is None:
            self._handlers = {
                'message': MessageStepHandler(self.registry_provider),
                'prompt': PromptStepHandler(self.registry_provider, self.completion_service),
                'user_input': UserInputStepHandler(),
                'invoke': InvokeStepHandler()
            }
        return self._handlers
    
    async def get_handler_for_step(self, step: Step) -> StepHandler:
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
