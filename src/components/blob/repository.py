

from src.core.models import Blob
from src.components.base_repository import BaseRepository


class BlobRepository(BaseRepository[Blob]):
    def __init__(self):
        super().__init__(Blob)
        self.table_name = "blobs"
