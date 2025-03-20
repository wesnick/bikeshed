from typing import Dict, Any, List, Optional, Union, AsyncGenerator
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config_types import SessionTemplate, Step
from src.core.registry import Registry
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

    def __init__(self,
                 get_db: async_sessionmaker[AsyncSession],
                 registry: Registry,
                 llm_service):
        """
        Initialize the WorkflowService with required dependencies.
        
        Args:
            get_db: async generator for getting database session
            registry: Registry instance
            llm_service: Service for interacting with language models
        """
        # Create persistence provider
        self.persistence = DatabasePersistenceProvider(get_db)

        # Create step handlers
        self.handlers = {
            'message': MessageStepHandler(registry),
            'prompt': PromptStepHandler(registry, llm_service),
            'user_input': UserInputStepHandler(),
            'invoke': InvokeStepHandler()
        }

        # Create workflow engine
        self.engine = WorkflowEngine(self.persistence, self.handlers)
        self.registry = registry

    async def create_session_from_template(
            self,
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
        session = await self.persistence.create_session(session_data)

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

    async def run_workflow(self, session: Session) -> None:
        while True:
            exec_result = await self.engine.execute_next_step(session)

            if not exec_result.success:
                break

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

    async def create_workflow_graph(self, session: Session) -> Optional[str]:
        """Create a visualization of the workflow"""
        return await WorkflowVisualizer.create_graph(session)
        
    async def analyze_workflow_dependencies(self, template: SessionTemplate) -> Dict[str, Any]:
        """
        Analyze a workflow template to identify input requirements and output provisions.
        
        Returns a dictionary with:
        - required_inputs: Dict of input variables needed by steps
        - provided_outputs: Dict of output variables provided by steps
        - missing_inputs: Dict of inputs not satisfied by previous steps
        """
        required_inputs = {}
        provided_outputs = {}
        missing_inputs = {}
        
        # Analyze each step for inputs and outputs
        for i, step in enumerate(template.steps):
            step_id = step.name
            
            # Analyze step for required inputs
            step_inputs = self._extract_step_inputs(step)
            if step_inputs:
                required_inputs[step_id] = step_inputs
                
                # Check if these inputs are satisfied by previous steps
                unsatisfied_inputs = {}
                for input_name, input_info in step_inputs.items():
                    if not any(input_name in outputs for outputs in list(provided_outputs.values())):
                        unsatisfied_inputs[input_name] = input_info
                
                if unsatisfied_inputs:
                    missing_inputs[step_id] = unsatisfied_inputs
            
            # Analyze step for provided outputs
            step_outputs = self._extract_step_outputs(step)
            if step_outputs:
                provided_outputs[step_id] = step_outputs
        
        return {
            "required_inputs": required_inputs,
            "provided_outputs": provided_outputs,
            "missing_inputs": missing_inputs
        }

    def _extract_step_inputs(self, step: Step) -> Dict[str, Dict[str, Any]]:
        """Extract input requirements from a step"""
        inputs = {}
        
        # Extract based on step type
        if step.type == "prompt":
            if step.template:
                prompt = self.registry.get_prompt(step.template)
                for arg in prompt.arguments:
                    inputs[arg.name] = {
                        "description": arg.description,
                        "required": arg.required
                    }
            if step.template_args:
                for arg_name in step.template_args:
                    if arg_name in inputs:
                        inputs[arg_name]["description"] = inputs[arg_name]["description"] + ' (superseded by `template_args`)'
                        inputs[arg_name]["required"] = False
        
        elif step.type == "invoke":
            if step.args:
                for arg_name in step.args:
                    inputs[arg_name] = {
                        "description": f"Input for function argument: {arg_name}",
                        "required": True
                    }
        
        elif step.type == "user_input":
            # User input steps themselves don't require inputs, they provide them
            pass
        
        elif step.type == "message":
            if step.template_args:
                for arg_name in step.template_args:
                    inputs[arg_name] = {
                        "description": f"Input for message template argument: {arg_name}",
                        "required": True
                    }
        
        return inputs

    def _extract_step_outputs(self, step: Step) -> Dict[str, Dict[str, Any]]:
        """Extract outputs provided by a step"""
        outputs = {}
        
        # Extract based on step type
        if step.type == "prompt":
            outputs["result"] = {
                "description": f"Output from prompt step: {step.name}",
                "source_step": step.name
            }

        elif step.type == "invoke":
            outputs["result"] = {
                "description": f"Output from function call: {step.name}",
                "source_step": step.name
            }

        elif step.type == "user_input":
            outputs["user_input"] = {
                "description": f"User provided input from step: {step.name}",
                "source_step": step.name
            }
        
        return outputs
