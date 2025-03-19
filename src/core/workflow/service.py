from typing import Dict, Any, List, Optional, Union
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config_types import SessionTemplate, Step
from src.models.models import Session
from src.core.workflow.engine import WorkflowEngine, WorkflowTransitionResult
from src.core.workflow.persistence import DatabasePersistenceProvider
from src.core.workflow.handlers.message import MessageStepHandler
from src.core.workflow.handlers.prompt import PromptStepHandler
from src.core.workflow.handlers.user_input import UserInputStepHandler
from src.core.workflow.handlers.invoke import InvokeStepHandler
from src.core.workflow.visualization import WorkflowVisualizer


class WorkflowService:
    """Service for managing workflow state machines"""

    def __init__(self, db_factory, registry_provider, llm_service):
        # Create persistence provider
        self.persistence = DatabasePersistenceProvider(db_factory)

        # Create step handlers
        self.handlers = {
            'message': MessageStepHandler(),
            'prompt': PromptStepHandler(registry_provider, llm_service),
            'user_input': UserInputStepHandler(),
            'invoke': InvokeStepHandler()
        }

        # Create workflow engine
        self.engine = WorkflowEngine(self.persistence, self.handlers)

        # Create visualizer
        self.visualizer = WorkflowVisualizer()

    async def create_session_from_template(
            self,
            db: AsyncSession,
            template: SessionTemplate,
            description: Optional[str] = None,
            goal: Optional[str] = None,
            initial_data: Optional[Dict] = None
    ) -> Session:
        """Create a new session from a template"""
        # Create session data
        session_data = {
            "id": uuid.uuid4(),
            "description": description or template.description,
            "goal": goal or template.goal,
            "template": template,
            "status": "created",
            "workflow_data": initial_data or {}
        }

        # Create session in database
        session = await self.persistence.create_session(db, session_data)

        # Initialize workflow
        return await self.engine.initialize_session(session)

    async def get_session(self, session_id: uuid.UUID) -> Optional[Session]:
        """Get a session by ID and initialize its workflow"""
        session = await self.persistence.load_session(session_id)
        if not session:
            return None

        return await self.engine.initialize_session(session)

    async def execute_next_step(
            self, session_id: uuid.UUID
    ) -> WorkflowTransitionResult:
        """Execute the next step in a workflow"""
        session = await self.get_session(session_id)
        if not session:
            return WorkflowTransitionResult(
                success=False,
                state="unknown",
                message=f"Session {session_id} not found"
            )

        return await self.engine.execute_next_step(session)

    async def provide_user_input(
            self,
            session_id: uuid.UUID,
            user_input: Union[str, Dict[str, Any]]
    ) -> WorkflowTransitionResult:
        """Provide user input for a waiting step"""
        session = await self.get_session(session_id)
        if not session:
            return WorkflowTransitionResult(
                success=False,
                state="unknown",
                message=f"Session {session_id} not found"
            )

        if session.status != 'waiting_for_input':
            return WorkflowTransitionResult(
                success=False,
                state=session.current_state,
                message="Session is not waiting for input"
            )

        # Handle different input types
        if 'missing_variables' in session.workflow_data:
            # For variable inputs
            if not isinstance(user_input, dict):
                return WorkflowTransitionResult(
                    success=False,
                    state=session.current_state,
                    message="Expected dictionary for variable inputs"
                )

            # Update variables
            variables = session.workflow_data.get('variables', {})
            variables.update(user_input)
            session.workflow_data['variables'] = variables

            # Clear missing variables flag
            session.workflow_data.pop('missing_variables')
        else:
            # For user_input steps
            session.workflow_data['user_input'] = user_input

        # Save changes
        await self.persistence.save_session(session)

        # Execute next step
        return await self.engine.execute_next_step(session)

    async def create_workflow_graph(self, session_id: uuid.UUID) -> Optional[str]:
        """Create a visualization of the workflow"""
        session = await self.get_session(session_id)
        if not session:
            return None

        return await self.visualizer.create_graph(session)