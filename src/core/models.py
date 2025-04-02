import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, TypeVar, ClassVar, Set
from enum import Enum

from pydantic import BaseModel, Field, model_validator, ConfigDict
from transitions.extensions import AsyncGraphMachine

from src.core.config_types import DialogTemplate, Step


class MessageStatus(str, Enum):
    CREATED = "created"       # The message has been created, but is incomplete, possible a stub
    PENDING = "pending"       # The message is complete, but hasn't been sent
    DELIVERED = "delivered"   # The message has been sent
    FAILED = "failed"         # Some type of error happened and should be considered incomplete


class DialogStatus(str, Enum):
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


# Define a TypeVar for the mixin
T = TypeVar('T', bound='DBModelMixin')

class DBModelMixin:
    """
    Mixin for Pydantic models that correspond to database tables.
    Provides metadata about field persistence and relationships.
    """
    # Class variables to store metadata
    __db_table__: ClassVar[str] = ""
    __non_persisted_fields__: ClassVar[Set[str]] = set()
    __unique_fields__: ClassVar[Set[str]] = {'id'} # Default unique field is 'id'

    def model_dump_db(self, **kwargs) -> Dict[str, Any]:
        """Dump model data excluding non-persisted fields."""
        return {k: v for k, v in self.model_dump().items() if v is not None and (self.__non_persisted_fields__ is None or k not in self.__non_persisted_fields__)}


class Message(BaseModel, DBModelMixin):
    __db_table__ = "messages"
    __non_persisted_fields__ = {'children', 'parent'}
    __unique_fields__ = {'id'}

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    parent_id: Optional[uuid.UUID] = None
    dialog_id: uuid.UUID

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


class Dialog(BaseModel, DBModelMixin):
    __db_table__ = "dialogs"
    __non_persisted_fields__ = {'machine', 'messages', 'created_at', 'updated_at'}
    __unique_fields__ = {'id'}

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    description: Optional[str] = None
    goal: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    template: Optional[DialogTemplate] = None

    # Workflow state fields
    status: DialogStatus = DialogStatus.PENDING
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
        """Return the first message in this dialog"""
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

class Root(BaseModel, DBModelMixin):
    __db_table__ = "roots"
    __non_persisted_fields__ = {'files', 'created_at'}
    __unique_fields__ = {'uri'} # URI is the primary key

    uri: str  # The root URI (Primary Key)
    created_at: Optional[datetime] = None
    extra: Optional[Dict[str, Any]] = None  # For additional metadata

    # Relationships
    files: List["RootFile"] = Field(default_factory=list)

class RootFile(BaseModel, DBModelMixin):
    __db_table__ = "root_files"
    __non_persisted_fields__ = {'root'}
    __unique_fields__ = {'root_uri', 'path'} # Composite primary key

    root_uri: str # Foreign key referencing Root.uri
    name: str  # Filename
    path: str  # Path relative to the root (Part of Primary Key)
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


class Blob(BaseModel, DBModelMixin):
    """
    A media object similar to schema.org MediaObject.
    Represents a file with metadata, with the actual bytes stored on disk.
    """
    __db_table__ = "blobs"
    __non_persisted_fields__: ClassVar[Set[str]] = {'created_at', 'updated_at'} # Add timestamp fields
    __unique_fields__ = {'id'} # Or perhaps sha256 if available and enforced?

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str  # Name of the media object
    description: Optional[str] = None  # Description of the media object
    content_type: str  # MIME type of the media object
    content_url: str  # URL or file path where the actual bytes are stored
    byte_size: Optional[int] = None  # Size of the media object in bytes
    sha256: Optional[str] = None  # SHA-256 hash of the media object for integrity verification
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata about the media object

    @model_validator(mode='after')
    def validate_content_type(self) -> 'Blob':
        """Validate that the content_type is a valid MIME type"""
        # Basic validation - could be enhanced with a more comprehensive check
        if '/' not in self.content_type:
            raise ValueError("content_type must be a valid MIME type (e.g., 'image/jpeg')")
        return self


class Tag(BaseModel, DBModelMixin):
    """
    A tag entity that can be hierarchically organized using ltree paths.
    Used for categorizing, filtering, and organizing content.  And triggering workflow.
    """
    __db_table__ = "tags"
    __non_persisted_fields__: ClassVar[Set[str]] = {'created_at', 'updated_at'}  # Add timestamp fields
    __unique_fields__ = {'id'}  # ID is the primary key

    id: str  # Human-readable string ID
    path: str  # Hierarchical path using ltree format
    name: str  # Display name of the tag
    description: Optional[str] = None  # Optional description
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @model_validator(mode='after')
    def validate_path_format(self) -> 'Tag':
        """Validate that the path follows the ltree format"""
        import re
        # Basic validation for ltree format: lowercase letters, numbers, and underscores separated by dots
        if not re.match(r'^([a-z0-9_]+\.)*[a-z0-9_]+$', self.path):
            raise ValueError("path must follow ltree format (e.g., 'category.subcategory')")
        return self


class StashItem(BaseModel):
    """
    An item in a stash collection. Can be text, a blob reference, or a registry item reference.
    """
    type: str  # "text", "blob", "registry"
    content: str  # Text content or reference ID
    metadata: Optional[Dict[str, Any]] = None


class Stash(BaseModel, DBModelMixin):
    """
    A collection of text entries, blobs, and registry item references.
    Acts as a container for various types of content.
    """
    __db_table__ = "stashes"
    __non_persisted_fields__: ClassVar[Set[str]] = {'created_at', 'updated_at'}
    __unique_fields__ = {'id'}  # ID is the primary key

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str  # Name of the stash
    description: Optional[str] = None  # Description of the stash
    items: List[StashItem] = Field(default_factory=list)  # Items in the stash
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata
