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
    template = Column(JSONB, nullable=True)

    # Relationships
    messages = relationship("Message", back_populates="session")

    @property
    def first_message(self):
        """Return the first message in this session"""
        if not self.messages:
            return None
        from sqlalchemy import asc, select
        from sqlalchemy.orm import selectinload
        return sorted(self.messages, key=lambda m: m.timestamp)[0] if self.messages else None

