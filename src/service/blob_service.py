import os
import uuid
import hashlib
import shutil
from pathlib import Path
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
        content_type: str,
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
        
        # Create the storage path for this blob
        blob_path = self._get_blob_path(blob_id)
        os.makedirs(os.path.dirname(blob_path), exist_ok=True)
        
        # Write the file to storage and calculate hash/size
        with open(blob_path, 'wb') as f:
            while chunk := file.read(8192):
                sha256_hash.update(chunk)
                byte_size += len(chunk)
                f.write(chunk)
        
        # Create the blob record
        blob = Blob(
            id=blob_id,
            name=name,
            description=description,
            content_type=content_type,
            content_url=self._get_relative_blob_path(blob_id),
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
        # Use magic to determine MIME type
        # mime_type = magic.from_file(str(file_path), mime=True)

        return await self.create_blob(
            conn=conn,
            name=upload_file.filename or "unnamed_file",
            content_type=upload_file.content_type or "application/octet-stream",
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
        blob_path = self._get_blob_path(blob_id)
        if os.path.exists(blob_path):
            os.remove(blob_path)
        
        # Delete from database
        return await self.repository.delete(conn, blob_id)
    
    def get_blob_content_path(self, blob_id: UUID) -> str:
        """Get the filesystem path to a blob's content"""
        return self._get_blob_path(blob_id)

    @staticmethod
    def _get_relative_blob_path(blob_id: UUID) -> str:
        """Get the storage path for a blob"""
        # Use the first 2 chars of the UUID as a subdirectory to avoid too many files in one dir
        blob_id_str = str(blob_id)
        return os.path.join(blob_id_str[:2], blob_id_str)

    def _get_blob_path(self, blob_id: UUID) -> str:
        """Get the storage path for a blob"""
        return os.path.join(self.storage_path, self._get_relative_blob_path(blob_id))
