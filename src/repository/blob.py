

from src.models.models import Blob
from src.repository.base import BaseRepository


class BlobRepository(BaseRepository[Blob]):
    def __init__(self):
        super().__init__(Blob)
        self.table_name = "blobs"
