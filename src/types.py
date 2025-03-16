from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID
from pydantic import BaseModel, Field


class MessageBase(BaseModel):
    role: str = 'user'
    model: Optional[str] = None
    text: str
    mime_type: str = "text/plain"
    extra: Optional[Dict[str, Any]] = None


class MessageCreate(MessageBase):
    session_id: UUID
    parent_id: Optional[UUID] = None


class ProjectSpecification(BaseModel):
    name: str
    overview: str
    duration_weeks: Optional[int]
    core_feature_details: list[str]



class ProjectMilestones(BaseModel):
    milestones: List[str] = []
