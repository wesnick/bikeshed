import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, model_validator, ConfigDict
from transitions.extensions import AsyncGraphMachine

from src.core.config_types import SessionTemplate, Step


class MessageStatus(str, Enum):
    CREATED = "created"       # The message has been created, but is incomplete, possible a stub
    PENDING = "pending"       # The message is complete, but hasn't been sent
    DELIVERED = "delivered"   # The message has been sent
    FAILED = "failed"         # Some type of error happened and should be considered incomplete


class SessionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_FOR_INPUT = "waiting_for_input"


class WorkflowData(BaseModel):
    current_step_index: int = 0
    step_results: Dict[str, Any] = Field(default_factory=dict)
    variables: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    missing_variables: List[str] = Field(default_factory=list)
    user_input: Optional[str] = None


class Message(BaseModel):
    __non_persisted_fields__ = ['children', 'parent']

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    parent_id: Optional[uuid.UUID] = None
    session_id: uuid.UUID

    role: str  # user, assistant, system
    model: Optional[str] = None
    text: str
    status: MessageStatus = MessageStatus.CREATED
    mime_type: str = "text/plain"
    timestamp: datetime = Field(default_factory=datetime.now)
    extra: Optional[Dict[str, Any]] = None  # For LLM parameters, UI customization, etc.

    # These will be populated when relationships are loaded
    children: List["Message"] = Field(default_factory=list)
    parent: Optional["Message"] = None

    # custom validations
    @model_validator(mode='after')
    def validate_text_or_extra(self) -> 'Message':
        if self.role == 'assistant' and not self.model:
            raise ValueError("Model must be set for assistant messages")
        return self


class Session(BaseModel):
    __non_persisted_fields__ = ['machine', 'messages']

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    description: Optional[str] = None
    goal: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    template: Optional[SessionTemplate] = None

    # Workflow state fields
    status: SessionStatus = SessionStatus.PENDING
    current_state: str = "start"  # Current state in the workflow
    workflow_data: Optional[WorkflowData] = Field(default_factory=WorkflowData)
    error: Optional[str] = None  # For storing error information

    # Relationships
    messages: List[Message] = Field(default_factory=list)

    # Instance variables - not persisted
    machine: Optional[AsyncGraphMachine] = Field(exclude=True, default=None)

    model_config = ConfigDict(
        extra='allow',
        arbitrary_types_allowed=True
    )


    @property
    def first_message(self) -> Optional[Message]:
        """Return the first message in this session"""
        if not self.messages:
            return None
        return sorted(self.messages, key=lambda m: m.timestamp)[0] if self.messages else None

    def get_current_step(self) -> Optional[Step]:
        """Get the current step from the template based on workflow data"""
        if not self.template or not self.workflow_data:
            return None

        current_index = self.workflow_data.current_step_index
        enabled_steps = [step for step in self.template.steps if step.enabled]

        if current_index < len(enabled_steps):
            return enabled_steps[current_index]
        return None

    def get_next_step_name(self) -> Optional[str]:
        """Get the next step from the template based on workflow data"""
        if not self.template or not self.workflow_data:
            return None

        current_index = self.workflow_data.current_step_index
        enabled_steps = [step for step in self.template.steps if step.enabled]

        if current_index + 1 < len(enabled_steps):
            return f"step_{current_index + 1}"
        return None


    def is_complete(self) -> bool:
        """Check if the workflow is complete"""
        if not self.template or not self.workflow_data:
            return False

        current_index = self.workflow_data.current_step_index
        enabled_steps = [step for step in self.template.steps if step.enabled]

        return current_index >= len(enabled_steps)

    def get_step_result(self, step_name: str) -> Optional[Dict[str, Any]]:
        """Get the result of a specific step"""
        if not self.workflow_data:
            return None

        return self.workflow_data.step_results.get(step_name)

class Root(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    uri: str  # The root URI
    created_at: datetime = Field(default_factory=datetime.now)
    last_accessed_at: datetime = Field(default_factory=datetime.now)
    extra: Optional[Dict[str, Any]] = None  # For additional metadata

    # Relationships
    files: List["RootFile"] = Field(default_factory=list)

class RootFile(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    root_id: uuid.UUID
    name: str  # Filename
    path: str  # Path relative to the root
    extension: Optional[str] = None  # File extension
    mime_type: Optional[str] = None
    size: Optional[int] = None  # File size in bytes
    atime: Optional[datetime] = None  # Last access time
    mtime: Optional[datetime] = None  # Last modification time
    ctime: Optional[datetime] = None  # Creation time (platform dependent)
    extra: Optional[Dict[str, Any]] = None  # For additional metadata

    # Relationships
    root: Optional[Root] = None

    @model_validator(mode='after')
    def validate_unique_path(self) -> 'RootFile':
        # This would be handled at the database level in a real implementation
        # Here we just provide a placeholder for validation logic
        return self


class Blob(BaseModel):
    """
    A media object similar to schema.org MediaObject.
    Represents a file with metadata, with the actual bytes stored on disk.
    """
    __non_persisted_fields__ = []
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str  # Name of the media object
    description: Optional[str] = None  # Description of the media object
    content_type: str  # MIME type of the media object
    content_url: str  # URL or file path where the actual bytes are stored
    byte_size: Optional[int] = None  # Size of the media object in bytes
    sha256: Optional[str] = None  # SHA-256 hash of the media object for integrity verification
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata about the media object

    @model_validator(mode='after')
    def validate_content_type(self) -> 'Blob':
        """Validate that the content_type is a valid MIME type"""
        # Basic validation - could be enhanced with a more comprehensive check
        if '/' not in self.content_type:
            raise ValueError("content_type must be a valid MIME type (e.g., 'image/jpeg')")
        return self
