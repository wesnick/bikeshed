import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Callable, Awaitable

from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Boolean, JSON, Table
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship, mapped_column
from transitions.extensions.asyncio import AsyncMachine

from src.core.config_types import SessionTemplate, Step
from .embedded_type import PydanticType

Base = declarative_base()

# Set naming convention for consistency
POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}
Base.metadata.naming_convention = POSTGRES_INDEXES_NAMING_CONVENTION

class Message(Base):
    __tablename__ = 'messages'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id = Column(UUID(as_uuid=True), ForeignKey('messages.id'), nullable=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey('sessions.id'), nullable=False)

    role = Column(String(50), nullable=False)  # user, assistant, system
    model = Column(String(100), nullable=True)
    text = Column(Text, nullable=False)
    status = Column(String(50), default='created')  # created, pending, delivered, failed, etc.
    mime_type = Column(String(100), default='text/plain')
    timestamp = Column(DateTime, default=datetime.now)
    extra = Column(JSONB, nullable=True)  # For LLM parameters, UI customization, etc.

    # Relationships
    children = relationship("Message", back_populates="parent", lazy="selectin",
                           cascade="all, delete-orphan", remote_side=[parent_id])
    parent = relationship("Message", remote_side=[id], back_populates="children")
    session = relationship("Session", back_populates="messages")



class Session(Base):
    __tablename__ = 'sessions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    description = Column(Text, nullable=True)
    goal = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    template: Optional[SessionTemplate] = Column(PydanticType(SessionTemplate), nullable=True)
    
    # Workflow state fields
    status = Column(String(50), default='pending')  # pending, running, paused, completed, failed, waiting_for_input
    current_state = Column(String(100), nullable=True)  # Current state in the workflow
    workflow_data = Column(JSONB, nullable=True)  # For storing workflow state data
    error = Column(Text, nullable=True)  # For storing error information

    # Relationships
    messages = relationship("Message", back_populates="session")

    # Instance variables
    machine: Optional[AsyncMachine] = None
    _temp_messages: List[Message] = []

    @property
    def first_message(self):
        """Return the first message in this session"""
        if not self.messages:
            return None
        from sqlalchemy import asc, select
        from sqlalchemy.orm import selectinload
        return sorted(self.messages, key=lambda m: m.timestamp)[0] if self.messages else None
    
    def get_current_step(self) -> Optional[Step]:
        """Get the current step from the template based on workflow data"""
        if not self.template or not self.workflow_data:
            return None
            
        current_index = self.workflow_data.get('current_step_index', 0)
        enabled_steps = [step for step in self.template.steps if step.enabled]
        
        if current_index < len(enabled_steps):
            return enabled_steps[current_index]
        return None
    
    def is_complete(self) -> bool:
        """Check if the workflow is complete"""
        if not self.template or not self.workflow_data:
            return False
            
        current_index = self.workflow_data.get('current_step_index', 0)
        enabled_steps = [step for step in self.template.steps if step.enabled]
        
        return current_index >= len(enabled_steps)
    
    def get_step_result(self, step_name: str) -> Optional[Dict[str, Any]]:
        """Get the result of a specific step"""
        if not self.workflow_data or 'step_results' not in self.workflow_data:
            return None
            
        return self.workflow_data['step_results'].get(step_name)
    
    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a workflow variable"""
        if not self.workflow_data or 'variables' not in self.workflow_data:
            return default
            
        return self.workflow_data['variables'].get(name, default)
    
    def set_variable(self, name: str, value: Any) -> None:
        """Set a workflow variable"""
        if not self.workflow_data:
            self.workflow_data = {}
            
        if 'variables' not in self.workflow_data:
            self.workflow_data['variables'] = {}
            
        self.workflow_data['variables'][name] = value

