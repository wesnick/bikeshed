import os
import uuid
import hashlib
import shutil
import magic
from typing import Optional, List, Dict, Any, BinaryIO
from uuid import UUID

from fastapi import UploadFile
from psycopg import AsyncConnection

from src.models.models import Blob
from src.repository.blob import BlobRepository


class BlobService:
    """Service for managing blob objects"""
    
    def __init__(self, storage_path: str = "var/blobs"):
        self.repository = BlobRepository()
        self.storage_path = storage_path
        # Ensure storage directory exists
        os.makedirs(self.storage_path, exist_ok=True)
    
    async def create_blob(
        self, 
        conn: AsyncConnection,
        name: str,
        content_type: Optional[str],
        file: BinaryIO,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Blob:
        """Create a new blob from a file-like object"""
        # Generate a unique ID for the blob
        blob_id = uuid.uuid4()
        
        # Calculate file hash and size
        sha256_hash = hashlib.sha256()
        byte_size = 0
        
        # Create a temporary file to detect content type if not provided
        temp_file_path = os.path.join(self.storage_path, f"temp_{blob_id}")
        with open(temp_file_path, 'wb') as temp_f:
            # Read the file in chunks to handle large files
            file_content = bytearray()
            while chunk := file.read(8192):
                file_content.extend(chunk)
                sha256_hash.update(chunk)
                byte_size += len(chunk)
                temp_f.write(chunk)
        
        # Detect content type if not provided
        if not content_type:
            content_type = magic.from_file(temp_file_path, mime=True)
        
        # Get file extension from original name
        _, ext = os.path.splitext(name)
        
        # Create the storage path for this blob with extension
        blob_path = self._get_blob_path(blob_id, ext)
        os.makedirs(os.path.dirname(blob_path), exist_ok=True)
        
        # Move the temporary file to the final location
        shutil.move(temp_file_path, blob_path)
        
        # Create the blob record
        blob = Blob(
            id=blob_id,
            name=name,
            description=description,
            content_type=content_type,
            content_url=self._get_relative_blob_path(blob_id, ext),
            byte_size=byte_size,
            sha256=sha256_hash.hexdigest(),
            metadata=metadata or {}
        )
        
        # Save to database
        return await self.repository.create(conn, blob)
    
    async def create_blob_from_upload(
        self,
        conn: AsyncConnection,
        upload_file: UploadFile,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Blob:
        """Create a new blob from a FastAPI UploadFile"""
        return await self.create_blob(
            conn=conn,
            name=upload_file.filename or "unnamed_file",
            content_type=upload_file.content_type,  # May be None, will be detected by create_blob
            file=upload_file.file,
            description=description,
            metadata=metadata
        )
    
    async def get_blob(self, conn: AsyncConnection, blob_id: UUID) -> Optional[Blob]:
        """Get a blob by ID"""
        return await self.repository.get_by_id(conn, blob_id)

    async def list_blobs(
        self, 
        conn: AsyncConnection, 
        limit: int = 100, 
        offset: int = 0
    ) -> List[Blob]:
        """List all blobs"""
        return await self.repository.get_all(conn, limit, offset)

    async def delete_blob(self, conn: AsyncConnection, blob_id: UUID) -> bool:
        """Delete a blob by ID"""
        blob = await self.repository.get_by_id(conn, blob_id)
        if not blob:
            return False
        
        # Delete the file from storage
        if os.path.exists(os.path.join(self.storage_path, blob.content_url)):
            os.remove(os.path.join(self.storage_path, blob.content_url))
        
        # Delete from database
        return await self.repository.delete(conn, blob_id)

    @staticmethod
    def _get_relative_blob_path(blob_id: UUID, extension: str) -> str:
        """
        Get the relative storage path for a blob
        
        Args:
            blob_id: The UUID of the blob
            extension: Optional file extension including the dot (e.g., '.jpg')
        """
        # Use the first 2 chars of the UUID as a subdirectory to avoid too many files in one dir
        blob_id_str = str(blob_id)
        return os.path.join(blob_id_str[:2], f"{blob_id_str}{extension}")

    def _get_blob_path(self, blob_id: UUID, extension: str) -> str:
        """
        Get the absolute storage path for a blob
        
        Args:
            blob_id: The UUID of the blob
            extension: Optional file extension including the dot (e.g., '.jpg')
        """
        return os.path.join(self.storage_path, self._get_relative_blob_path(blob_id, extension))
