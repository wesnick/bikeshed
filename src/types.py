from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID
from pydantic import BaseModel, Field
from src.core.config_loader import register_schema


class SessionTemplateCreationRequest(BaseModel):
    description: Optional[str] = None
    goal: Optional[str] = None
    input: Optional[dict[str, Any]] = None

    model_config = {
        'allow_extra': 'allow'
    }

class MessageBase(BaseModel):
    role: str = 'user'
    model: Optional[str] = 'faker' # @TODO
    text: str
    mime_type: str = "text/plain"
    extra: Optional[Dict[str, Any]] = None


class MessageCreate(MessageBase):
    session_id: UUID
    parent_id: Optional[UUID] = None
    # Button fields - these will be empty strings when present
    send_button: Optional[str] = None
    continue_button: Optional[str] = None

    # This will hold which button was pressed
    button_pressed: Optional[str] = Field(None, exclude=True)

    def model_post_init(self, __context: Any) -> None:
        """Determine which button was pressed after model initialization"""
        if self.send_button is not None:
            self.button_pressed = "send"
        elif self.continue_button is not None:
            self.button_pressed = "continue"


@register_schema("Project specification with core features and overview")
class ProjectSpecification(BaseModel):
    """Project specification with core features and overview"""
    name: str
    final_specification: str
    next_steps: list[str]


@register_schema("Project milestones tracking")
class ProjectMilestones(BaseModel):
    """Project milestones tracking"""
    milestones: List[str] = []
