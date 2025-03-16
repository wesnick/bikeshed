import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Boolean, JSON, Table
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship, mapped_column

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

# # Association tables for many-to-many relationships
# artifact_scratchpad = Table(
#     'artifact_scratchpad',
#     Base.metadata,
#     Column('artifact_id', UUID(as_uuid=True), ForeignKey('artifacts.id'), primary_key=True),
#     Column('scratchpad_id', UUID(as_uuid=True), ForeignKey('scratchpads.id'), primary_key=True)
# )


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
    # artifacts = relationship("Artifact", back_populates="source_message")


class Session(Base):
    __tablename__ = 'sessions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # flow_id = Column(UUID(as_uuid=True), ForeignKey('flows.id'), nullable=True)

    summary = Column(Text, nullable=True)
    goal = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=True)
    strategy = Column(String(100), nullable=True)  # task decomposition, etc.
    created_at = Column(DateTime, default=datetime.now)
    # template_id = Column(UUID(as_uuid=True), ForeignKey('flow_templates.id'), nullable=True)

    # Relationships
    messages = relationship("Message", back_populates="session")
    # flow = relationship("Flow", back_populates="sessions")
    # artifacts = relationship("Artifact", back_populates="source_session")
    # template = relationship("FlowTemplate", back_populates="derived_sessions")

    @property
    def first_message(self):
        """Return the first message in this session"""
        if not self.messages:
            return None
        from sqlalchemy import asc, select
        from sqlalchemy.orm import selectinload
        return sorted(self.messages, key=lambda m: m.timestamp)[0] if self.messages else None


class Flow(Base):
    __tablename__ = 'flows'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    goal = Column(Text, nullable=True)
    strategy = Column(String(100), nullable=True)  # workflow, sequence, etc.

    # State machine properties
    current_state = Column(String(100), nullable=True)
    workflow_definition = Column(JSONB, nullable=True)  # YAML workflow as JSON

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    template_id = Column(UUID(as_uuid=True), ForeignKey('flow_templates.id'), nullable=True)

    # Relationships
    # sessions = relationship("Session", back_populates="flow")
    # artifacts = relationship("Artifact", back_populates="source_flow")
    # template = relationship("FlowTemplate", back_populates="derived_flows")


# class Artifact(Base):
#     __tablename__ = 'artifacts'
#
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#
#     name = Column(String(255), nullable=False)
#     description = Column(Text, nullable=True)
#     mime_type = Column(String(100), nullable=False)
#     content_path = Column(String(255), nullable=True)  # Path to stored content if binary
#     content_text = Column(Text, nullable=True)  # Direct content if text
#
#     # Can be linked to any source
#     source_message_id = Column(UUID(as_uuid=True), ForeignKey('messages.id'), nullable=True)
#     source_session_id = Column(UUID(as_uuid=True), ForeignKey('sessions.id'), nullable=True)
#     source_flow_id = Column(UUID(as_uuid=True), ForeignKey('flows.id'), nullable=True)
#
#     created_at = Column(DateTime, default=datetime.now)
#     updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
#     extra = Column(JSONB, nullable=True)  # For file size, dimensions, etc.
#
#     # Relationships
#     # source_message = relationship("Message", back_populates="artifacts")
#     # source_session = relationship("Session", back_populates="artifacts")
#     # source_flow = relationship("Flow", back_populates="artifacts")
#     # scratchpads = relationship("ScratchPad", secondary=artifact_scratchpad, back_populates="scratchpads")
#
#
# class FlowTemplate(Base):
#     __tablename__ = 'flow_templates'
#
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#
#     name = Column(String(255), nullable=False)
#     description = Column(Text, nullable=True)
#     definition = Column(JSONB, nullable=False)  # Template definition as JSON
#
#     created_at = Column(DateTime, default=datetime.now)
#     updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
#
#     # Relationships
#     # derived_flows = relationship("Flow", back_populates="template")
#     # derived_sessions = relationship("Session", back_populates="template")
#
#
# class ScratchPad(Base):
#     __tablename__ = 'scratchpads'
#
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#
#     name = Column(String(255), nullable=False)
#     description = Column(Text, nullable=True)
#     notes = Column(JSONB, nullable=True)  # Additional free-form notes
#
#     created_at = Column(DateTime, default=datetime.now)
#     updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
#
#     # Relationships
#     # artifacts = relationship("Artifact", secondary=artifact_scratchpad, back_populates="scratchpads")
