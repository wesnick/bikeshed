from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from psycopg import AsyncConnection
import aiofiles
import aiofiles.os
import magic

from src.core.models import Root, RootFile
from src.repository import root_repository, root_file_repository
from src.service.logging import logger

class FileScanner:

    def __init__(self, conn: AsyncConnection):
        self.conn = conn
        self.root_repo = root_repository
        self.root_file_repo = root_file_repository

    async def _scan_entry(self, root_uri: str, entry_path: Path) -> Optional[RootFile]:
        """Scan a file or directory and create a RootFile Pydantic model."""
        try:
            stat = await aiofiles.os.stat(entry_path)
            is_dir = await aiofiles.os.path.isdir(entry_path)
            # Ensure root_uri is a Path object for relative_to
            root_path_obj = Path(root_uri)
            relative_path = entry_path.relative_to(root_path_obj)

            if is_dir:
                mime_type = "inode/directory"
                extension = None
                size = 0
            else:
                # Use magic to determine MIME type for files
                mime_type = magic.from_file(str(entry_path), mime=True)
                extension = entry_path.suffix
                size = stat.st_size

            root_file = RootFile(
                root_uri=root_uri,
                name=entry_path.name,
                path=str(relative_path),
                extension=extension,
                mime_type=mime_type,
                size=size,
                atime=datetime.fromtimestamp(stat.st_atime),
                mtime=datetime.fromtimestamp(stat.st_mtime),
                ctime=datetime.fromtimestamp(stat.st_ctime),
            )
            return root_file
        except FileNotFoundError:
            logger.warning(f"Entry not found during scan: {entry_path}")
            return None
        except Exception as e:
            logger.error(f"Error scanning entry {entry_path}: {e}", exc_info=True)
            return None

    async def _get_existing_files(self, root_uri: str) -> Dict[str, RootFile]:
        """Get all existing files for a root from the database using the repository."""
        files = await self.root_file_repo.get_files_by_root(self.conn, root_uri)
        return {file.path: file for file in files}

    async def _collect_filesystem_files(self, root: Root) -> Dict[str, Path]:
        """Collect all files and directories in the filesystem for a root."""
        # Ensure root.uri is a Path object
        root_path = Path(root.uri)
        filesystem_entries = {}

        async def _collect_entries_recursive(directory: Path):
            try:
                entries = await aiofiles.os.scandir(directory)
                for entry in entries:
                    entry_path = Path(entry.path)
                    relative_path = entry_path.relative_to(root_path)
                    filesystem_entries[str(relative_path)] = entry_path # Add both files and dirs

                    if entry.is_dir():
                        # Ensure recursive call uses the internal helper name
                        await _collect_entries_recursive(entry_path) # Recurse into subdirectories
            except Exception as e:
                logger.error(f"Error collecting files from {directory}: {e}", exc_info=True)

        # Initial call to the recursive helper
        await _collect_entries_recursive(root_path)
        return filesystem_entries

    async def _delete_removed_files(self, root_uri: str, paths_to_delete: List[str]) -> int: # Renaming might be good later
        """Delete entries (files or directories) using the repository."""
        deleted_count = 0
        if not paths_to_delete:
            return 0
        for path in paths_to_delete:
            try:
                deleted = await self.root_file_repo.delete(self.conn, root_uri, path)
                if deleted:
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting entry {path} for root {root_uri}: {e}", exc_info=True)
        return deleted_count

    async def sync_directory(self, root: Root) -> None:
        """
        Synchronize the database with the current state of the filesystem for a given root.
        Uses bulk operations for efficiency.
        """
        logger.info(f"Starting sync for root: {root.uri}")
        added_count = 0
        updated_count = 0
        deleted_count = 0
        files_to_upsert: List[RootFile] = []

        try:
            # Get existing files from database via repository
            existing_files = await self._get_existing_files(root.uri)
            logger.debug(f"Found {len(existing_files)} existing entries in DB for {root.uri}")

            # Get current files and directories from filesystem
            filesystem_entries = await self._collect_filesystem_files(root) # Method name kept for now
            logger.debug(f"Found {len(filesystem_entries)} entries (files/dirs) on disk for {root.uri}")

            # Find entries to update, add, or remove
            existing_paths = set(existing_files.keys())
            filesystem_paths = set(filesystem_entries.keys())

            paths_to_update = existing_paths.intersection(filesystem_paths)
            paths_to_add = filesystem_paths - existing_paths
            paths_to_delete = list(existing_paths - filesystem_paths) # Convert set to list

            logger.debug(f"Entries to add: {len(paths_to_add)}")
            logger.debug(f"Entries to update/check: {len(paths_to_update)}")
            logger.debug(f"Entries to delete: {len(paths_to_delete)}")

            # Process entries to add
            for path_str in paths_to_add:
                entry_path = filesystem_entries[path_str]
                scanned_entry = await self._scan_entry(root.uri, entry_path)
                if scanned_entry:
                    files_to_upsert.append(scanned_entry)
                    added_count += 1 # Tentative count

            # Process entries to update
            for path_str in paths_to_update:
                existing_entry = existing_files[path_str]
                entry_path = filesystem_entries[path_str]
                try:
                    stat = await aiofiles.os.stat(entry_path)
                    is_dir = await aiofiles.os.path.isdir(entry_path) # Check if it's a directory

                    needs_update = False
                    # Check if entry changed based on mtime (always)
                    if datetime.fromtimestamp(stat.st_mtime) != existing_entry.mtime:
                        needs_update = True
                    # Additionally check size for files
                    elif not is_dir and stat.st_size != existing_entry.size:
                         needs_update = True
                    # Additionally check mime_type change (e.g., file became dir or vice-versa)
                    elif existing_entry.mime_type == "inode/directory" and not is_dir:
                         needs_update = True
                    elif existing_entry.mime_type != "inode/directory" and is_dir:
                         needs_update = True


                    if needs_update:
                        scanned_entry = await self._scan_entry(root.uri, entry_path)
                        if scanned_entry:
                            files_to_upsert.append(scanned_entry)
                            updated_count += 1 # Tentative count
                except FileNotFoundError:
                    logger.warning(f"Entry {entry_path} found in DB but not on disk during update check. Will be deleted.")
                    # If entry disappeared between listing and stat, it will be handled by delete
                    if path_str not in paths_to_delete:
                         paths_to_delete.append(path_str)
                except Exception as e:
                    logger.error(f"Error checking entry for update {entry_path}: {e}", exc_info=True)


            async with self.conn.transaction():
                # Bulk insert/update changed/new files
                if files_to_upsert:
                    logger.info(f"Upserting {len(files_to_upsert)} files for root {root.uri}")
                    # bulk_create handles ON CONFLICT DO UPDATE
                    results = await self.root_file_repo.bulk_create(self.conn, files_to_upsert)
                    # Note: bulk_create returns the upserted models. We could refine counts here if needed.
                    logger.debug(f"Upsert result count: {len(results)}")


                # Delete removed entries
                if paths_to_delete:
                    logger.info(f"Deleting {len(paths_to_delete)} entries for root {root.uri}")
                    deleted_count = await self._delete_removed_files(root.uri, paths_to_delete) # Removed self.conn argument


            # Final logging outside transaction
            logger.info(f"Sync completed for {root.uri}:")
            # Note: Counts are based on intent before bulk operations. Actual DB changes might differ slightly on conflict/error.
            logger.info(f"  - Added/Updated: {len(files_to_upsert)} (approx {added_count} added, {updated_count} updated)")
            logger.info(f"  - Deleted: {deleted_count}")

        except Exception as e:
            logger.error(f"Error synchronizing directory {root.uri}: {e}", exc_info=True)
            # Ensure transaction is rolled back if error occurs before commit
            # (Handled by async context manager and db_operation decorator)

    async def create_root_and_scan(self, directory_path: str, sync: bool = False) -> None:
        """
        Create a Root if it doesn't exist, and then scan the directory.

        Args:
            directory_path: Path to the directory to scan.
            sync: If True, perform a full sync (add, update, delete).
                  If False (default), only add new files and update existing ones (no deletes).
                  A sync is always performed if the root is newly created.
        """
        path_str = str(Path(directory_path).resolve())
        path_obj = Path(path_str) # Use Path object for checks

        if not path_obj.is_dir():
            raise ValueError(f"'{directory_path}' is not a valid directory.")

        root: Optional[Root] = None
        is_new_root = False

        # Check/Create Root using repository
         # Wrap repository calls potentially needing transaction in one block
        async with self.conn.transaction():
            root = await self.root_repo.get_by_uri(self.conn, path_str)
            if root is None:
                logger.info(f"Root not found for {path_str}, creating new one.")
                new_root_model = Root(uri=path_str) # Let DB handle created_at/updated_at
                root = await self.root_repo.create(self.conn, new_root_model)
                logger.info(f"Root created: {root.uri}")
                is_new_root = True
                sync = True # Always sync fully for a new root
            else:
                logger.info(f"Found existing root: {root.uri}")

        if root is None:
             # This should not happen if DB/repo logic is correct, but defensively check
             logger.error(f"Failed to get or create root for {path_str}")
             return

        # Perform the sync operation (outside the root creation transaction)
        # sync_directory now handles add/update/delete based on comparison
        await self.sync_directory(root)

    async def sync_root(self, directory_path: str) -> None:
        """
        Convenience method to fully sync (add, update, delete) a root directory.
        Creates the root if it doesn't exist.
        """
        # create_root_and_scan with sync=True now handles the full sync logic
        await self.create_root_and_scan(directory_path, sync=True)

