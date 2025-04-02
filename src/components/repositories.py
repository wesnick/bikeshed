from src.components.dialog.repository import DialogRepository
from src.components.message.repository import MessageRepository
from src.components.tag.repository import TagRepository
from src.components.tag.entity_repository import EntityTagRepository
from src.components.blob.repository import BlobRepository
from src.components.stash.repository import StashRepository
from src.components.stash.entity_repository import EntityStashRepository
from src.components.root.repository import RootRepository
from src.components.root.file_repository import RootFileRepository


# Create instances for dependency injection
dialog_repository = DialogRepository()
message_repository = MessageRepository()
tag_repository = TagRepository()
entity_tag_repository = EntityTagRepository()
blob_repository = BlobRepository()
stash_repository = StashRepository()
entity_stash_repository = EntityStashRepository()
root_repository = RootRepository()
root_file_repository = RootFileRepository()
