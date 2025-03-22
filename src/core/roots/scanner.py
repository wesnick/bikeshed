from datetime import datetime
from pathlib import Path
from psycopg import AsyncConnection
from src.models.models import Root, RootFile
import aiofiles
import aiofiles.os
import magic
import uuid
from typing import Optional, Callable, AsyncGenerator


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
            for entry in entries:
                entry_path = Path(entry.path)
                if entry.is_file():
                    root_file = await self._scan_file(root, entry_path)
                    if root_file:
                        # Insert the root_file using psycopg
                        await conn.execute(
                            """
                            INSERT INTO root_files (
                                id, root_id, name, path, extension, mime_type, 
                                size, atime, mtime, ctime
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                root_file.id, 
                                root_file.root_id, 
                                root_file.name, 
                                root_file.path, 
                                root_file.extension, 
                                root_file.mime_type, 
                                root_file.size, 
                                root_file.atime, 
                                root_file.mtime, 
                                root_file.ctime
                            )
                        )
                elif entry.is_dir():
                    await self._scan_directory_recursive(root, entry_path, conn)
        except Exception as e:
            print(f"Error scanning directory {directory_path}: {e}") # Use logger


    async def scan_directory(self, root: Root) -> None:
        """
        Recursively scan a directory and store file information in the database,
        associating files with the given Root.
        """
        async for conn in self.get_db():
            async with conn.transaction():
                directory_path = Path(root.uri)
                await self._scan_directory_recursive(root, directory_path, conn)

    async def create_root_and_scan(self, directory_path: str) -> None:
        """
        Create a Root if it doesn't exist, and then scan the directory.
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
                else:
                    root = Root(id=root_data[0], uri=root_data[1])
                    print(f"Root already exists: {root.uri} (ID: {root.id})")  # Use logger

        # Scan directory in a separate transaction
        await self.scan_directory(root)

