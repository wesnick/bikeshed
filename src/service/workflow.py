import asyncio
from typing import Dict, Any, Optional, List, Union, Callable
from uuid import UUID
import logging
from datetime import datetime

from transitions.extensions.asyncio import AsyncMachine
from transitions.extensions.factory import MachineFactory

from sqlalchemy.ext.asyncio import AsyncSession
from src.core.config_types import SessionTemplate, Step
from src.core import RunContext
from src.models.models import Session, Message
from src.repository.session import SessionRepository
from src.repository.message import MessageRepository
from src.dependencies import get_db

logger = logging.getLogger(__name__)

class WorkflowModel:
    """Model class for the state machine that handles workflow execution"""
    
    def __init__(self, session_id: UUID, template: SessionTemplate, service):
        self.session_id = session_id
        self.template = template
        self.service = service
        self.state = 'initial'  # Initial state
        
    async def execute_step(self, event):
        """Execute the current step in the workflow"""
        # Get the current step index from the state
        current_state = event.transition.dest
        if not current_state.startswith("step_"):
            return
            
        step_index = int(current_state.split("_")[1])
        step = self.template.steps[step_index]
        
        # Update session status
        async with get_db() as db:
            await self.service.session_repo.update(db, self.session_id, {
                "status": "running",
                "current_state": current_state
            })

        try:
            # Create a message for this step
            async with get_db() as db:
                message = await self.service._create_step_message(db, self.session_id, step)

            # Execute the step based on its type
            if step.type == "message":
                await self.service._execute_message_step(self.session_id, step, message)
            elif step.type == "prompt":
                await self.service._execute_prompt_step(self.session_id, step, message)
            elif step.type == "user_input":
                # For user_input, we'll pause the workflow and wait for input
                async with get_db() as db:
                    session = await self.service.session_repo.get_by_id(db, self.session_id)
                    await self.service.session_repo.update(db, self.session_id, {
                        "status": "paused",
                        "workflow_data": {
                            **(session.workflow_data or {}),
                            "current_message_id": str(message.id)
                        }
                    })
                return
            elif step.type == "invoke":
                await self.service._execute_invoke_step(self.session_id, step, message)

            # If we reach here, we can proceed to the next step
            # The state machine will handle this automatically

        except Exception as e:
            logger.exception(f"Error executing step {step_index}")
            async with get_db() as db:
                await self.service.session_repo.update(db, self.session_id, {
                    "status": "failed",
                    "error": str(e)
                })
            # Trigger failure
            machine = self.service.active_machines[self.session_id]
            await machine.trigger('fail')
    
    async def on_workflow_completed(self, event):
        """Handle workflow completion"""
        # Update the session
        async with get_db() as db:
            await self.service.session_repo.update(db, self.session_id, {
                "status": "completed"
            })
    
    async def on_workflow_failed(self, event):
        """Handle workflow failure"""
        # Update the session
        async with get_db() as db:
            await self.service.session_repo.update(db, self.session_id, {
                "status": "failed"
            })

class WorkflowService:
    """Service for managing workflow execution based on session templates"""

    def __init__(
        self,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
    ):
        self.session_repo = session_repo
        self.message_repo = message_repo
        self.active_machines: Dict[UUID, AsyncMachine] = {}

    async def get_session(self, db: AsyncSession, session_id: UUID) -> Optional[Session]:
        """Get a session by ID"""
        return await self.session_repo.get_by_id(db, session_id)

    async def create_state_machine(
        self,
        session: Session,
        template: Optional[SessionTemplate] = None
    ) -> AsyncMachine:
        """Create a state machine for a session"""
        if not template and not session.template:
            raise ValueError("Template is required to create a state machine")

        template_to_use = template or session.template

        # Create state machine
        machine = self._create_state_machine(session, template_to_use)

        # Store the machine
        self.active_machines[session.id] = machine

        return machine

    def _create_state_machine(
        self,
        session: Session,
        template: SessionTemplate
    ) -> AsyncMachine:
        """Create a state machine from a session template"""
        # Extract states from template steps
        states = ["initial"] + [f"step_{i}" for i in range(len(template.steps))] + ["completed", "failed"]

        # Create a workflow model that will handle the callbacks
        workflow_model = WorkflowModel(session.id, template, self)
        
        # Create the state machine with the workflow model
        machine_cls = MachineFactory.get_predefined(asyncio=True)
        machine = machine_cls(
            model=workflow_model,
            states=states,
            initial='initial',
            send_event=True,
            auto_transitions=False,
        )
        
        # Add transitions after machine creation
        # Add initial transition
        machine.add_transition(
            trigger='start',
            source='initial',
            dest='step_0',
            before='execute_step'
        )

        # Add transitions between steps
        for i in range(len(template.steps) - 1):
            machine.add_transition(
                trigger=f'next_step_{i}',
                source=f'step_{i}',
                dest=f'step_{i+1}',
                before='execute_step'
            )

        # Add final transition
        machine.add_transition(
            trigger=f'next_step_{len(template.steps)-1}',
            source=f'step_{len(template.steps)-1}',
            dest='completed',
            before='on_workflow_completed'
        )

        # Add failure transitions from each step
        for i in range(len(template.steps)):
            machine.add_transition(
                trigger='fail',
                source=f'step_{i}',
                dest='failed',
                before='on_workflow_failed'
            )

        return machine

    def _create_step_callback(
        self,
        session_id: UUID,
        step_index: int,
        template: SessionTemplate
    ) -> Callable:
        """Create a callback function for executing a step"""
        step = template.steps[step_index]

        async def execute_step(event):
            session = event.model

            # Update session status
            async with get_db() as db:
                await self.session_repo.update(db, session_id, {
                    "status": "running",
                    "current_state": f"step_{step_index}"
                })

            try:
                # Create a message for this step
                async with get_db() as db:
                    message = await self._create_step_message(db, session_id, step)

                # Execute the step based on its type
                if step.type == "message":
                    await self._execute_message_step(session_id, step, message)
                elif step.type == "prompt":
                    await self._execute_prompt_step(session_id, step, message)
                elif step.type == "user_input":
                    # For user_input, we'll pause the workflow and wait for input
                    async with get_db() as db:
                        await self.session_repo.update(db, session_id, {
                            "status": "paused",
                            "workflow_data": {
                                **session.workflow_data,
                                "current_message_id": str(message.id)
                            }
                        })
                    return
                elif step.type == "invoke":
                    await self._execute_invoke_step(session_id, step, message)

                # Trigger the next step
                next_trigger = f"next_step_{step_index}"
                machine = self.active_machines[session_id]
                await machine.trigger(next_trigger)

            except Exception as e:
                logger.exception(f"Error executing step {step_index}")
                async with get_db() as db:
                    await self.session_repo.update(db, session_id, {
                        "status": "failed",
                        "error": str(e)
                    })
                await self.active_machines[session_id].trigger('fail')

        return execute_step

    async def _create_step_message(
        self,
        db: AsyncSession,
        session_id: UUID,
        step: Step
    ) -> Message:
        """Create a message for a step"""
        # Determine the role based on step type
        role = "system"
        if step.type == "message" and hasattr(step, "role"):
            role = step.role
        elif step.type == "prompt":
            role = "assistant"
        elif step.type == "user_input":
            role = "user"

        # Create the message
        message_data = {
            "session_id": session_id,
            "role": role,
            "text": "",  # Will be populated during execution
            "status": "pending",
            "timestamp": datetime.now(),
            "extra": {
                "step_type": step.type,
                "step_name": step.name,
            }
        }

        # Create the message in the database
        message = await self.message_repo.create(db, message_data)

        return message

    async def _execute_message_step(
        self,
        session_id: UUID,
        step: Step,
        message: Message
    ):
        """Execute a message step"""
        # Get the content from the step
        content = step.content if hasattr(step, "content") else ""

        # Update the message
        async with get_db() as db:
            await self.message_repo.update(db, message.id, {
                "text": content,
                "status": "delivered"
            })

    async def _execute_prompt_step(
        self,
        session_id: UUID,
        step: Step,
        message: Message
    ):
        """Execute a prompt step"""
        # In a real implementation, this would call the LLM
        # For now, we'll just update the message with placeholder text
        content = "This is a placeholder response for a prompt step"

        # Update the message
        async with get_db() as db:
            await self.message_repo.update(db, message.id, {
                "text": content,
                "status": "delivered"
            })

    async def _execute_invoke_step(
        self,
        session_id: UUID,
        step: Step,
        message: Message
    ):
        """Execute an invoke step"""
        # In a real implementation, this would call the specified function
        # For now, we'll just update the message with placeholder text
        content = f"Executed function: {step.callable if hasattr(step, 'callable') else 'unknown'}"

        # Update the message
        async with get_db() as db:
            await self.message_repo.update(db, message.id, {
                "text": content,
                "status": "delivered"
            })

    async def _on_workflow_completed(self, event):
        """Handle workflow completion"""
        session = event.model
        session_id = session.id

        # Update the session
        async with get_db() as db:
            await self.session_repo.update(db, session_id, {
                "status": "completed"
            })

    async def _on_workflow_failed(self, event):
        """Handle workflow failure"""
        session = event.model
        session_id = session.id

        # Update the session
        async with get_db() as db:
            await self.session_repo.update(db, session_id, {
                "status": "failed"
            })

    async def start_workflow(self, db: AsyncSession, session_id: UUID) -> Session:
        """Start a workflow"""
        if session_id not in self.active_machines:
            raise ValueError(f"No workflow found for session {session_id}")

        machine = self.active_machines[session_id]
        
        # Start the workflow
        await machine.trigger('start')

        # Refresh the session
        session = await self.session_repo.get_by_id(db, session_id)

        return session

    async def resume_workflow(
        self,
        db: AsyncSession,
        session_id: UUID,
        user_input: Optional[str] = None
    ) -> Session:
        """Resume a paused workflow"""
        if session_id not in self.active_machines:
            raise ValueError(f"No workflow found for session {session_id}")

        machine = self.active_machines[session_id]
        session = await self.session_repo.get_by_id(db, session_id)

        if session.status != "paused":
            raise ValueError(f"Workflow is not paused: {session.status}")

        # If we have a current message and it's a user_input step
        if session.workflow_data and "current_message_id" in session.workflow_data:
            message_id = UUID(session.workflow_data["current_message_id"])
            # Update the message with the user input
            await self.message_repo.update(db, message_id, {
                "text": user_input or "",
                "status": "delivered"
            })

        # Get the current step index from the state
        current_step = session.current_state
        if not current_step.startswith("step_"):
            raise ValueError(f"Invalid current step: {current_step}")

        step_index = int(current_step.split("_")[1])

        # Trigger the next step
        next_trigger = f"next_step_{step_index}"
        await machine.trigger(next_trigger)

        # Refresh the session
        session = await self.session_repo.get_by_id(db, session_id)

        return session

    async def pause_workflow(self, db: AsyncSession, session_id: UUID) -> Session:
        """Pause a running workflow"""
        session = await self.session_repo.get_by_id(db, session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Update the session status
        session = await self.session_repo.update(db, session_id, {
            "status": "paused"
        })

        return session

    def generate_workflow_diagram(self, session_id: UUID, format: str = "mermaid") -> str:
        """Generate a diagram of the workflow"""
        if session_id not in self.active_machines:
            raise ValueError(f"No workflow found for session {session_id}")

        # Get the machine
        machine = self.active_machines[session_id]

        # Create a graph machine
        graph_machine_cls = MachineFactory.get_predefined(graph=True)
        graph_machine = graph_machine_cls(
            states=machine.states,
            transitions=machine.transitions,
            initial=machine.initial,
            auto_transitions=False,
            title=f"Workflow for Session {session_id}",
            show_conditions=True
        )

        # Get the graph
        graph = graph_machine.get_graph()

        # Return the diagram
        if format == "mermaid":
            return graph.draw(format="mermaid")
        else:
            # For graphviz, return the DOT representation
            return graph.string()
