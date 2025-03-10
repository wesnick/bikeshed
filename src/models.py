from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from src.database import metadata

Base = declarative_base(metadata=metadata)

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True, index=True)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system', etc.
    model = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    extra = Column(JSON, nullable=True)
    
    # Relationship to parent message
    parent = relationship("Message", remote_side=[id], backref="children")
    
    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, parent_id={self.parent_id})>"
    
    @classmethod
    def create_from_dict(cls, data):
        """Create a Message instance from a dictionary"""
        return cls(
            parent_id=data.get('parent_id'),
            role=data.get('role'),
            model=data.get('model'),
            content=data.get('content'),
            extra=data.get('extra')
        )
    
    def to_dict(self):
        """Convert Message to dictionary"""
        return {
            "id": str(self.id),
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "role": self.role,
            "model": self.model,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "extra": self.extra
        }

