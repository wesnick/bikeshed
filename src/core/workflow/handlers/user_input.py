from typing import Any
from src.core.workflow.engine import StepHandler
from src.core.config_types import UserInputStep, Step
from src.models.models import Session, Message

class UserInputHandler(StepHandler):
    """Handler for user_input steps"""

    async def can_handle(self, session: Session, step: Step) -> bool:
        """Check if the step can be handled"""


    async def handle(self, session: Session, step: Step) -> dict[str, Any]:
        """Handle a user_input step"""
