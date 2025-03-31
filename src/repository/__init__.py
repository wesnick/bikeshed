from src.repository.session import SessionRepository
from src.repository.message import MessageRepository
from src.repository.tag import TagRepository
from src.repository.blob import BlobRepository
from src.repository.stash import StashRepository
from src.repository.root import RootRepository
from src.repository.root_file import RootFileRepository

# Create instances for dependency injection
session_repository = SessionRepository()
message_repository = MessageRepository()
tag_repository = TagRepository()
blob_repository = BlobRepository()
stash_repository = StashRepository()
root_repository = RootRepository()
root_file_repository = RootFileRepository()
