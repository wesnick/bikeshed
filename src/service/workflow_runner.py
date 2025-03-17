from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from src.core.config_types import SessionTemplate
from src.core import RunContext
from src.models.models import Session
from src.service.workflow import WorkflowService
from src.service.session import SessionService

class WorkflowRunner:
    """Handles the execution of workflow steps with RunContext"""
    
    def __init__(
        self,
        workflow_service: WorkflowService,
        session_service: Optional[SessionService] = None
    ):
        self.workflow_service = workflow_service
        self.session_service = session_service or SessionService()
        self.active_contexts: Dict[UUID, RunContext] = {}
    
    async def create_and_run(
        self, 
        db: AsyncSession, 
        template: SessionTemplate,
        description: Optional[str] = None,
        goal: Optional[str] = None,
        initial_data: Optional[Dict[str, Any]] = None
    ) -> Session:
        """Create a session from template and run the workflow"""
        # Create context
        context = RunContext(
            deps=None,  # Will be populated as needed
            model=template.model,
            lookup=initial_data or {}
        )
        
        # Create the session
        session = await self.session_service.create_session_from_template(
            db,
            template,
            description,
            goal,
            context.lookup
        )
        
        # Store the context
        self.active_contexts[session.id] = context
        
        # Create and start the workflow
        await self.workflow_service.create_state_machine(session, template)
        session = await self.workflow_service.start_workflow(db, session.id)
        
        return session
    
    async def run_existing(self, db: AsyncSession, session_id: UUID) -> Session:
        """Run an existing workflow that's already been created"""
        session = await self.workflow_service.start_workflow(db, session_id)
        return session
    
    async def resume(
        self, 
        db: AsyncSession, 
        session_id: UUID, 
        user_input: Optional[str] = None
    ) -> Session:
        """Resume a paused workflow"""
        # Get or create context
        if session_id not in self.active_contexts:
            session = await self.workflow_service.get_session(db, session_id)
            if not session:
                raise ValueError(f"Session not found: {session_id}")
                
            # Create a new context from session data
            self.active_contexts[session_id] = RunContext(
                deps=None,
                model=session.template.model if session.template else None,
                lookup=session.workflow_data or {}
            )
        
        context = self.active_contexts[session_id]
        
        # Update the context with user input if provided
        if user_input is not None:
            context.lookup["user_input"] = user_input
        
        # Resume the workflow
        session = await self.workflow_service.resume_workflow(
            db,
            session_id,
            user_input
        )
        
        # Update the context with the session workflow data
        if session.workflow_data:
            context.lookup.update(session.workflow_data)
        
        return session
