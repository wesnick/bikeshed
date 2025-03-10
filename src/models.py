from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from src.database import metadata

Base = declarative_base(metadata=metadata)

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system', etc.
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, session_id={self.session_id})>"
    
    @classmethod
    def create_from_dict(cls, data):
        """Create a Message instance from a dictionary"""
        return cls(
            session_id=data.get('session_id', str(uuid.uuid4())),
            role=data.get('role'),
            content=data.get('content'),
            metadata=data.get('metadata')
        )

