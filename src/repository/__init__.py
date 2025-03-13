from src.repository.base import BaseRepository
from src.repository.flow import FlowRepository
from src.repository.session import SessionRepository
from src.repository.message import MessageRepository

# Create instances for dependency injection
flow_repository = FlowRepository()
session_repository = SessionRepository()
message_repository = MessageRepository()
