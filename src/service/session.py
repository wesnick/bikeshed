from typing import Dict, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config_types import SessionTemplate
from src.models.models import Session
from src.repository.session import SessionRepository
from src.service.logging import logger


async def create_session_from_template(
    db: AsyncSession,
    template: SessionTemplate,
    description: Optional[str] = None,
    goal: Optional[str] = None,
) -> Optional[Session]:
    """
    Create a new session from a template.

    Args:
        db: Database session
        template: Session template
        description: Optional description override
        goal: Optional goal override

    Returns:
        The created session or None if template not found
    """

    # Create the session
    session_repo = SessionRepository()

    # Use template values but override with provided values if any
    session_data = {
        "id": uuid.uuid4(),
        "description": description or template.description,
        "goal": goal or template.goal,
        "template": template
    }

    # Create and return the session
    return await session_repo.create(db, session_data)
