from src.models.models import Session, Message, Tag, Blob, Stash, Root, RootFile
from src.repository.factory import RepositoryFactory

# Create instances for dependency injection
session_repository = RepositoryFactory.get_repository(Session)
message_repository = RepositoryFactory.get_repository(Message)
tag_repository = RepositoryFactory.get_repository(Tag)
blob_repository = RepositoryFactory.get_repository(Blob)
stash_repository = RepositoryFactory.get_repository(Stash)
root_repository = RepositoryFactory.get_repository(Root)
root_file_repository = RepositoryFactory.get_repository(RootFile)
