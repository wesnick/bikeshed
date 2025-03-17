from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from src.core.config_types import SessionTemplate
from src.core import RunContext
from src.models.models import Session
from src.service.workflow import WorkflowService

class WorkflowRunner:
    """Handles the execution of workflow steps with RunContext"""
    
    def __init__(
        self,
        workflow_service: WorkflowService,
        session_id: UUID,
        template: SessionTemplate,
        initial_data: Optional[Dict[str, Any]] = None
    ):
        self.workflow_service = workflow_service
        self.session_id = session_id
        self.template = template
        self.context = RunContext(
            deps=None,  # Will be populated as needed
            model=template.model,
            lookup=initial_data or {}
        )
    
    async def run(self, db: AsyncSession) -> Session:
        """Run the workflow"""
        # Create the workflow
        session = await self.workflow_service.create_workflow(
            db,
            self.session_id,
            self.template,
            self.context.lookup
        )
        
        # Start the workflow
        session = await self.workflow_service.start_workflow(db, self.session_id)
        
        return session
    
    async def resume(self, db: AsyncSession, user_input: Optional[str] = None) -> Session:
        """Resume a paused workflow"""
        # Update the context with user input if provided
        if user_input is not None:
            self.context.lookup["user_input"] = user_input
        
        # Resume the workflow
        session = await self.workflow_service.resume_workflow(
            db,
            self.session_id,
            user_input
        )
        
        # Update the context with the session workflow data
        if session.workflow_data:
            self.context.lookup.update(session.workflow_data)
        
        return session
