from src.repository.session import SessionRepository
from src.repository.message import MessageRepository
from src.repository.tag import TagRepository
from src.repository.blob import BlobRepository
from src.repository.stash import StashRepository

# Create instances for dependency injection
session_repository = SessionRepository()
message_repository = MessageRepository()
tag_repository = TagRepository()
blob_repository = BlobRepository()
stash_repository = StashRepository()
