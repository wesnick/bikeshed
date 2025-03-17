from typing import Dict, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config_loader import SessionTemplateLoader
from src.core.registry import Registry
from src.models.models import Session
from src.repository.session import SessionRepository
from src.service.logging import logger


async def create_session_from_template(
    db: AsyncSession,
    template_name: str,
    description: Optional[str] = None,
    goal: Optional[str] = None,
) -> Optional[Session]:
    """
    Create a new session from a template.
    
    Args:
        db: Database session
        template_name: Name of the template to use
        description: Optional description override
        goal: Optional goal override
        
    Returns:
        The created session or None if template not found
    """
    # Load the template
    registry = Registry()
    loader = SessionTemplateLoader(registry)
    
    # Try to find the template in the default location
    templates = loader.load_from_file("config/session_templates.yaml")
    
    if template_name not in templates:
        logger.error(f"Template '{template_name}' not found")
        return None
    
    template = templates[template_name]
    
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
