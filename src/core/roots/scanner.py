from datetime import datetime
from pathlib import Path
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from src.models.models import Root, RootFile
import aiofiles
import aiofiles.os
import magic
from sqlalchemy import select


class FileScanner:

    def __init__(self, async_session_factory: async_sessionmaker[AsyncSession]):
        self.async_session_factory = async_session_factory

    async def _scan_file(self, root: Root, file_path: Path) -> RootFile:
        """Scan a single file and create a RootFile entity."""
        try:
            stat = await aiofiles.os.stat(file_path)
            relative_path = file_path.relative_to(root.uri)

            # Use magic to determine MIME type
            mime_type = magic.from_file(str(file_path), mime=True)

            root_file = RootFile(
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

    async def _scan_directory_recursive(self, root: Root, directory_path: Path, session: AsyncSession):
        """Recursively scan a directory and create RootFile entities."""
        try:
            entries = await aiofiles.os.scandir(directory_path)
            for entry in entries:
                entry_path = Path(entry.path)
                if await entry.is_file():
                    root_file = await self._scan_file(root, entry_path)
                    if root_file:
                        session.add(root_file)
                elif await entry.is_dir():
                    await self._scan_directory_recursive(root, entry_path, session)
        except Exception as e:
            print(f"Error scanning directory {directory_path}: {e}") # Use logger


    async def scan_directory(self, root: Root) -> None:
        """
        Recursively scan a directory and store file information in the database,
        associating files with the given Root.
        """
        async with self.async_session_factory() as session:
            async with session.begin():
                directory_path = Path(root.uri)
                await self._scan_directory_recursive(root, directory_path, session)

    async def create_root_and_scan(self, directory_path: str) -> None:
        """
        Create a Root if it doesn't exist, and then scan the directory.
        """
        async with self.async_session_factory() as session:
            async with session.begin():
                path = Path(directory_path).resolve()
                if not path.is_dir():
                    raise ValueError(f"'{directory_path}' is not a valid directory.")

                # Check if Root exists
                stmt = select(Root).where(Root.uri == str(path))
                result = await session.execute(stmt)
                root = result.scalar_one_or_none()

                if root is None:
                    # Create Root object
                    root = Root(uri=str(path))
                    session.add(root)
                    await session.commit()  # Commit to get the root ID
                    await session.refresh(root) # Refresh to load
                    print(f"Root created: {root.uri} (ID: {root.id})") # Use logger
                else:
                    print(f"Root already exists: {root.uri} (ID: {root.id})") # Use logger

                await self.scan_directory(root)

