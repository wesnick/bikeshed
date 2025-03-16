from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID
from pydantic import BaseModel, Field
from src.core.schema_loader import register_schema


class MessageBase(BaseModel):
    role: str = 'user'
    model: Optional[str] = None
    text: str
    mime_type: str = "text/plain"
    extra: Optional[Dict[str, Any]] = None


class MessageCreate(MessageBase):
    session_id: UUID
    parent_id: Optional[UUID] = None


@register_schema("Project specification with core features and overview")
class ProjectSpecification(BaseModel):
    name: str
    overview: str
    duration_weeks: Optional[int]
    core_feature_details: list[str]



@register_schema("Project milestones tracking")
class ProjectMilestones(BaseModel):
    milestones: List[str] = []
