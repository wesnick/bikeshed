from typing import List
from pydantic import BaseModel
from src.core.config_loader import register_schema


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
