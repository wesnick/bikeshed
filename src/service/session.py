from typing import Dict, Optional, Union
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config_types import SessionTemplate
from src.models.models import Session
from src.repository.session import SessionRepository
from src.service.logging import logger


class SessionService:
    """Service for managing sessions"""
    
    def __init__(self, session_repo: Optional[SessionRepository] = None):
        self.session_repo = session_repo or SessionRepository()
    
    async def create_ad_hoc_session(
        self,
        db: AsyncSession,
        description: str,
        goal: Optional[str] = None,
        initial_data: Optional[Dict] = None
    ) -> Session:
        """
        Create a new ad-hoc session without a workflow.
        
        Args:
            db: Database session
            description: Session description
            goal: Optional session goal
            initial_data: Optional initial data for the session
            
        Returns:
            The created session
        """
        session_data = {
            "id": uuid.uuid4(),
            "description": description,
            "goal": goal,
            "status": "ad-hoc",
            "workflow_data": initial_data or {}
        }
        
        return await self.session_repo.create(db, session_data)
    
    async def create_session_from_template(
        self,
        db: AsyncSession,
        template: SessionTemplate,
        description: Optional[str] = None,
        goal: Optional[str] = None,
        initial_data: Optional[Dict] = None
    ) -> Session:
        """
        Create a new session from a template.

        Args:
            db: Database session
            template: Session template
            description: Optional description override
            goal: Optional goal override
            initial_data: Optional initial data for the workflow

        Returns:
            The created session
        """
        # Use template values but override with provided values if any
        session_data = {
            "id": uuid.uuid4(),
            "description": description or template.description,
            "goal": goal or template.goal,
            "template": template,
            "status": "pending",
            "current_state": "initial",
            "workflow_data": initial_data or {}
        }

        # Create and return the session
        return await self.session_repo.create(db, session_data)
