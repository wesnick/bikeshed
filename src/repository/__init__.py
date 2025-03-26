from src.repository.session import SessionRepository
from src.repository.message import MessageRepository
from src.repository.tag import TagRepository

# Create instances for dependency injection
session_repository = SessionRepository()
message_repository = MessageRepository()
tag_repository = TagRepository()
