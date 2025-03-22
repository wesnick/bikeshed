from datetime import datetime
from pathlib import Path
from psycopg import AsyncConnection
from psycopg.cursor import AsyncCursor
from src.models.models import Root, RootFile
import aiofiles
import aiofiles.os
import magic
import uuid
from typing import Optional, Callable, AsyncGenerator, Dict, List, Set, Tuple


class FileScanner:

    def __init__(self, get_db: Callable[[], AsyncGenerator[AsyncConnection, None]]):
        self.get_db = get_db

    async def _scan_file(self, root: Root, file_path: Path) -> RootFile:
        """Scan a single file and create a RootFile entity."""
        try:
            stat = await aiofiles.os.stat(file_path)
            relative_path = file_path.relative_to(root.uri)

            # Use magic to determine MIME type
            mime_type = magic.from_file(str(file_path), mime=True)

            root_file = RootFile(
                id=uuid.uuid4(),
                root_id=root.id,
                name=file_path.name,
                path=str(relative_path),
                extension=file_path.suffix,
                mime_type=mime_type,
                size=stat.st_size,
                atime=datetime.fromtimestamp(stat.st_atime),
                mtime=datetime.fromtimestamp(stat.st_mtime),
                ctime=datetime.fromtimestamp(stat.st_ctime),
            )
            return root_file
        except Exception as e:
            print(f"Error scanning file {file_path}: {e}") # Use logger
            return None

    async def _scan_directory_recursive(self, root: Root, directory_path: Path, conn: AsyncConnection):
        """Recursively scan a directory and create RootFile entities."""
        try:
            entries = await aiofiles.os.scandir(directory_path)
            root_files = []
            
            # First, collect all files in this directory
            for entry in entries:
                entry_path = Path(entry.path)
                if entry.is_file():
                    root_file = await self._scan_file(root, entry_path)
                    if root_file:
                        root_files.append((
                            str(root_file.id),
                            str(root_file.root_id),
                            root_file.name,
                            root_file.path,
                            root_file.extension,
                            root_file.mime_type,
                            root_file.size,
                            root_file.atime,
                            root_file.mtime,
                            root_file.ctime
                        ))
            
            # Use COPY to insert all files in a batch if there are any
            if root_files:
                async with conn.cursor() as cursor:
                    async with cursor.copy(
                        "COPY root_files (id, root_id, name, path, extension, mime_type, size, atime, mtime, ctime) FROM STDIN"
                    ) as copy:
                        for record in root_files:
                            await copy.write_row(record)
            
            # Then recursively process subdirectories
            for entry in entries:
                entry_path = Path(entry.path)
                if entry.is_dir():
                    await self._scan_directory_recursive(root, entry_path, conn)
        except Exception as e:
            print(f"Error scanning directory {directory_path}: {e}") # Use logger


    async def scan_directory(self, root: Root) -> None:
        """
        Recursively scan a directory and store file information in the database,
        associating files with the given Root.
        
        This is a fast initial load that uses batch insertion.
        For updating existing data, use sync_directory instead.
        """
        async for conn in self.get_db():
            async with conn.transaction():
                directory_path = Path(root.uri)
                await self._scan_directory_recursive(root, directory_path, conn)
                
    async def _get_existing_files(self, root_id: uuid.UUID, conn: AsyncConnection) -> Dict[str, RootFile]:
        """Get all existing files for a root from the database."""
        existing_files = {}
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT id, root_id, name, path, extension, mime_type, size, 
                       atime, mtime, ctime
                FROM root_files
                WHERE root_id = %s
                """,
                (str(root_id),)
            )
            async for row in cursor:
                root_file = RootFile(
                    id=row[0],
                    root_id=row[1],
                    name=row[2],
                    path=row[3],
                    extension=row[4],
                    mime_type=row[5],
                    size=row[6],
                    atime=row[7],
                    mtime=row[8],
                    ctime=row[9]
                )
                existing_files[root_file.path] = root_file
        return existing_files
    
    async def _collect_filesystem_files(self, root: Root) -> Dict[str, Path]:
        """Collect all files in the filesystem for a root."""
        root_path = Path(root.uri)
        filesystem_files = {}
        
        async def collect_files(directory: Path):
            try:
                entries = await aiofiles.os.scandir(directory)
                for entry in entries:
                    entry_path = Path(entry.path)
                    if entry.is_file():
                        relative_path = entry_path.relative_to(root_path)
                        filesystem_files[str(relative_path)] = entry_path
                    elif entry.is_dir():
                        await collect_files(entry_path)
            except Exception as e:
                print(f"Error collecting files from {directory}: {e}")  # Use logger
                
        await collect_files(root_path)
        return filesystem_files
    
    async def _update_file(self, root_file: RootFile, file_path: Path, conn: AsyncConnection) -> None:
        """Update an existing file in the database if it has changed."""
        try:
            stat = await aiofiles.os.stat(file_path)
            file_mtime = datetime.fromtimestamp(stat.st_mtime)
            
            # If modification time is different, update the file
            if file_mtime != root_file.mtime or stat.st_size != root_file.size:
                # Use magic to determine MIME type
                mime_type = magic.from_file(str(file_path), mime=True)
                
                await conn.execute(
                    """
                    UPDATE root_files
                    SET name = %s, extension = %s, mime_type = %s, size = %s,
                        atime = %s, mtime = %s, ctime = %s
                    WHERE id = %s
                    """,
                    (
                        file_path.name,
                        file_path.suffix,
                        mime_type,
                        stat.st_size,
                        datetime.fromtimestamp(stat.st_atime),
                        file_mtime,
                        datetime.fromtimestamp(stat.st_ctime),
                        str(root_file.id)
                    )
                )
        except Exception as e:
            print(f"Error updating file {file_path}: {e}")  # Use logger
    
    async def _insert_new_files(self, root: Root, new_file_paths: List[Tuple[str, Path]], conn: AsyncConnection) -> None:
        """Insert new files into the database."""
        root_files = []
        
        for relative_path_str, file_path in new_file_paths:
            root_file = await self._scan_file(root, file_path)
            if root_file:
                root_files.append((
                    str(root_file.id),
                    str(root_file.root_id),
                    root_file.name,
                    root_file.path,
                    root_file.extension,
                    root_file.mime_type,
                    root_file.size,
                    root_file.atime,
                    root_file.mtime,
                    root_file.ctime
                ))
        
        # Use COPY to insert all files in a batch if there are any
        if root_files:
            async with conn.cursor() as cursor:
                async with cursor.copy(
                    "COPY root_files (id, root_id, name, path, extension, mime_type, size, atime, mtime, ctime) FROM STDIN"
                ) as copy:
                    for record in root_files:
                        await copy.write_row(record)
    
    async def _delete_removed_files(self, root_id: uuid.UUID, paths_to_delete: List[str], conn: AsyncConnection) -> None:
        """Delete files that no longer exist in the filesystem."""
        if paths_to_delete:
            # Convert list to tuple for SQL IN clause
            placeholders = ','.join(['%s'] * len(paths_to_delete))
            await conn.execute(
                f"DELETE FROM root_files WHERE root_id = %s AND path IN ({placeholders})",
                (str(root_id), *paths_to_delete)
            )
    
    async def sync_directory(self, root: Root) -> None:
        """
        Synchronize the database with the current state of the filesystem.
        This will:
        1. Update existing files that have changed
        2. Add new files that aren't in the database
        3. Remove files from the database that no longer exist in the filesystem
        """
        async for conn in self.get_db():
            try:
                # Get existing files from database
                existing_files = await self._get_existing_files(root.id, conn)
                
                # Get current files from filesystem
                filesystem_files = await self._collect_filesystem_files(root)
                
                # Find files to update, add, or remove
                existing_paths = set(existing_files.keys())
                filesystem_paths = set(filesystem_files.keys())
                
                paths_to_update = existing_paths.intersection(filesystem_paths)
                paths_to_add = filesystem_paths - existing_paths
                paths_to_delete = existing_paths - filesystem_paths
                
                async with conn.transaction():
                    # Update existing files that might have changed
                    for path in paths_to_update:
                        await self._update_file(existing_files[path], filesystem_files[path], conn)
                    
                    # Insert new files
                    new_file_paths = [(path, filesystem_files[path]) for path in paths_to_add]
                    await self._insert_new_files(root, new_file_paths, conn)
                    
                    # Delete removed files
                    await self._delete_removed_files(root.id, list(paths_to_delete), conn)
                    
                print(f"Sync completed for {root.uri}:")  # Use logger
                print(f"  - Updated: {len(paths_to_update)} files")
                print(f"  - Added: {len(paths_to_add)} files")
                print(f"  - Removed: {len(paths_to_delete)} files")
                
            except Exception as e:
                print(f"Error synchronizing directory {root.uri}: {e}")  # Use logger

    async def create_root_and_scan(self, directory_path: str, sync: bool = False) -> None:
        """
        Create a Root if it doesn't exist, and then scan the directory.
        
        Args:
            directory_path: Path to the directory to scan
            sync: If True, use sync_directory instead of scan_directory to update existing files
        """
        path = Path(directory_path).resolve()
        if not path.is_dir():
            raise ValueError(f"'{directory_path}' is not a valid directory.")

        async for conn in self.get_db():
            async with conn.transaction():
                # Check if Root exists
                result = await conn.execute(
                    "SELECT id, uri FROM roots WHERE uri = %s",
                    (str(path),)
                )
                root_data = await result.fetchone()
                
                if root_data is None:
                    # Create Root object
                    root_id = uuid.uuid4()
                    await conn.execute(
                        "INSERT INTO roots (id, uri) VALUES (%s, %s)",
                        (root_id, str(path))
                    )
                    root = Root(id=root_id, uri=str(path))
                    print(f"Root created: {root.uri} (ID: {root.id})")  # Use logger
                    # For new roots, always do a full scan
                    sync = False
                else:
                    root = Root(id=root_data[0], uri=root_data[1])
                    print(f"Root already exists: {root.uri} (ID: {root.id})")  # Use logger

        # Process directory in a separate transaction
        if sync:
            await self.sync_directory(root)
        else:
            await self.scan_directory(root)
            
    async def sync_root(self, directory_path: str) -> None:
        """
        Convenience method to sync an existing root with the filesystem.
        Creates the root if it doesn't exist.
        """
        await self.create_root_and_scan(directory_path, sync=True)

