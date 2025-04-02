import pytest
from uuid import uuid4
from datetime import datetime

from psycopg import AsyncConnection
from psycopg.sql import SQL

from core.models import Root
from components.root.repository import RootRepository

pytestmark = pytest.mark.asyncio


@pytest.fixture
def root_repo() -> RootRepository:
    return RootRepository()


@pytest.fixture
def sample_root_file_data(sample_root_data: dict) -> dict:
    # Use the URI from sample_root_data
    return {
        "root_uri": sample_root_data["uri"],
        "name": "test_file.txt",
        "path": f"/test/path/{uuid4().hex}.txt", # Ensure unique path
        "extension": "txt",
        "mime_type": "text/plain",
        "size": 1024,
        "atime": datetime.now(),
        "mtime": datetime.now(),
        "ctime": datetime.now(),
        "extra": {"encoding": "utf-8"}
    }


@pytest.fixture
def sample_root_data() -> dict:
    return {
        "uri": f"file:///test/path/{uuid4().hex}",
        "extra": {"description": "Test root directory"}
    }


def _create_root_data(base_data: dict, **kwargs) -> dict:
    """Helper to create unique root data for tests."""
    data = base_data.copy()
    data.update(kwargs)
    return data


async def test_create_root(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    root_model = Root(**sample_root_data)
    created_root = await root_repo.create(db_conn_clean, root_model)

    assert created_root is not None
    assert created_root.uri == sample_root_data["uri"] # URI is the identifier now
    assert created_root.extra == sample_root_data["extra"]
    assert isinstance(created_root.created_at, datetime)


# Rename test_get_root_by_id to test_get_root_by_uri
async def test_get_root_by_uri(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    root_model = Root(**sample_root_data)
    created_root = await root_repo.create(db_conn_clean, root_model)

    # Fetch using the URI (which is the PK)
    fetched_root = await root_repo.get_by_uri(db_conn_clean, created_root.uri)

    assert fetched_root is not None
    assert fetched_root.uri == created_root.uri # Check URI equality
    assert fetched_root.extra == created_root.extra


async def test_get_root_by_uri_not_found(db_conn_clean: AsyncConnection, root_repo: RootRepository):
    non_existent_uri = f"file:///non/existent/{uuid4().hex}"
    fetched_root = await root_repo.get_by_uri(db_conn_clean, non_existent_uri)
    assert fetched_root is None


async def test_get_all_roots(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    # Test data remains the same, just how we create/assert changes slightly
    root1_data = _create_root_data(sample_root_data, uri=f"file:///test/all/{uuid4().hex}")
    root2_data = _create_root_data(sample_root_data, uri=f"file:///test/all/{uuid4().hex}")
    root1_model = Root(**root1_data)
    root2_model = Root(**root2_data)
    await root_repo.create(db_conn_clean, root1_model)
    await root_repo.create(db_conn_clean, root2_model)

    all_roots = await root_repo.get_all(db_conn_clean, limit=10)

    assert len(all_roots) == 2
    root_uris = {r.uri for r in all_roots}
    assert root1_data["uri"] in root_uris
    assert root2_data["uri"] in root_uris


async def test_update_root(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    root_model = Root(**sample_root_data)
    created_root = await root_repo.create(db_conn_clean, root_model)

    # Note: Updating the primary key (uri) is generally discouraged.
    # Here we update 'extra'. If BaseRepository.update needs the PK, pass the uri.
    update_data = {
        "extra": {"description": "Updated test root directory"}
    }
    # Assuming BaseRepository.update takes the PK (uri) and data
    updated_root = await root_repo.update(db_conn_clean, created_root.uri, update_data)

    assert updated_root is not None
    assert updated_root.uri == created_root.uri # URI should not change unless explicitly updated (and allowed)
    assert updated_root.extra == update_data["extra"]


async def test_update_root_not_found(db_conn_clean: AsyncConnection, root_repo: RootRepository):
    non_existent_uri = f"file:///non/existent/update/{uuid4().hex}"
    update_data = {"extra": {"description": "Attempted update"}}
    # Assuming BaseRepository.update takes the PK (uri)
    updated_root = await root_repo.update(db_conn_clean, non_existent_uri, update_data)
    assert updated_root is None


async def test_delete_root(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    root_model = Root(**sample_root_data)
    created_root = await root_repo.create(db_conn_clean, root_model)

    # Assuming BaseRepository.delete takes the PK (uri)
    deleted = await root_repo.delete(db_conn_clean, created_root.uri)
    assert deleted is True

    # Verify deletion by trying to fetch it again by URI
    fetched_root = await root_repo.get_by_uri(db_conn_clean, created_root.uri)
    assert fetched_root is None


async def test_delete_root_not_found(db_conn_clean: AsyncConnection, root_repo: RootRepository):
    non_existent_uri = f"file:///non/existent/delete/{uuid4().hex}"
    # Assuming BaseRepository.delete takes the PK (uri)
    deleted = await root_repo.delete(db_conn_clean, non_existent_uri)
    assert deleted is False


async def test_filter_roots(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    # Test data remains the same
    root1_data = _create_root_data(sample_root_data, uri=f"file:///test/filter/filter_test_1")
    root2_data = _create_root_data(sample_root_data, uri=f"file:///test/filter/filter_test_2")
    root1_model = Root(**root1_data)
    root2_model = Root(**root2_data)
    await root_repo.create(db_conn_clean, root1_model)
    await root_repo.create(db_conn_clean, root2_model)

    # Filter by the exact URI
    filtered_roots = await root_repo.filter(db_conn_clean, {"uri": "file:///test/filter/filter_test_2"})

    assert len(filtered_roots) == 1
    assert filtered_roots[0].uri == "file:///test/filter/filter_test_2"


async def test_get_recent_roots(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    root1_data = _create_root_data(sample_root_data, uri=f"file:///test/recent/old_root")
    root1_model = Root(**root1_data)
    created1 = await root_repo.create(db_conn_clean, root1_model)

    # Simulate time passing - update based on URI now
    await db_conn_clean.execute(
        SQL("UPDATE roots SET created_at = NOW() - INTERVAL '1 second' WHERE uri = %s"),
        (created1.uri,)
    )

    root2_data = _create_root_data(sample_root_data, uri=f"file:///test/recent/new_root")
    root2_model = Root(**root2_data)
    created2 = await root_repo.create(db_conn_clean, root2_model)

    recent_roots = await root_repo.get_recent_roots(db_conn_clean, limit=1)
    assert len(recent_roots) == 1
    assert recent_roots[0].uri == created2.uri # Check URI

    recent_roots_all = await root_repo.get_recent_roots(db_conn_clean, limit=5)
    assert len(recent_roots_all) == 2
    assert recent_roots_all[0].uri == created2.uri  # Newest first by URI
    assert recent_roots_all[1].uri == created1.uri


# test_get_root_by_uri is already defined above and covers this case.
# We can remove the duplicate definition.


async def test_get_with_files(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict, sample_root_file_data: dict):
    # Create a root
    root_model = Root(**sample_root_data)
    created_root = await root_repo.create(db_conn_clean, root_model)

    # Create file data linked to the created root's URI
    file1_data = sample_root_file_data.copy()
    file1_data["root_uri"] = created_root.uri
    file1_data["path"] = "/test/path/file1.txt" # Ensure unique paths if needed
    file1_data["name"] = "file1.txt"

    file2_data = sample_root_file_data.copy()
    file2_data["root_uri"] = created_root.uri
    file2_data["path"] = "/test/path/file2.txt"
    file2_data["name"] = "file2.txt"

    # Insert files directly into the database using the new schema
    from psycopg.types.json import Jsonb

    # Note: No 'id' column anymore, use root_uri
    await db_conn_clean.execute(
        """
        INSERT INTO root_files (root_uri, name, path, extension, mime_type, size, atime, mtime, ctime, extra)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            file1_data["root_uri"], file1_data["name"], file1_data["path"], file1_data["extension"],
            file1_data["mime_type"], file1_data["size"], file1_data["atime"], file1_data["mtime"], file1_data["ctime"],
            Jsonb(file1_data["extra"]) if file1_data["extra"] else None
        )
    )

    await db_conn_clean.execute(
        """
        INSERT INTO root_files (root_uri, name, path, extension, mime_type, size, atime, mtime, ctime, extra)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            file2_data["root_uri"], file2_data["name"], file2_data["path"], file2_data["extension"],
            file2_data["mime_type"], file2_data["size"], file2_data["atime"], file2_data["mtime"], file2_data["ctime"],
            Jsonb(file2_data["extra"]) if file2_data["extra"] else None
        )
    )

    # Get the root with its files using the root URI
    root_with_files = await root_repo.get_with_files(db_conn_clean, created_root.uri)

    assert root_with_files is not None
    assert root_with_files.uri == created_root.uri # Check URI
    assert len(root_with_files.files) == 2

    # Files should be ordered by path
    assert root_with_files.files[0].name == "file1.txt"
    assert root_with_files.files[1].name == "file2.txt"

    # Verify file properties
    assert root_with_files.files[0].root_uri == created_root.uri # Check root_uri
    assert root_with_files.files[0].extension == "txt"
    assert root_with_files.files[0].mime_type == "text/plain"


async def test_get_with_files_not_found(db_conn_clean: AsyncConnection, root_repo: RootRepository):
    non_existent_uri = f"file:///non/existent/files/{uuid4().hex}"
    root_with_files = await root_repo.get_with_files(db_conn_clean, non_existent_uri)
    assert root_with_files is None


async def test_get_with_files_no_files(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    # Create a root without any files
    root_model = Root(**sample_root_data)
    created_root = await root_repo.create(db_conn_clean, root_model)

    # Get the root with its files (should be empty) using the root URI
    root_with_files = await root_repo.get_with_files(db_conn_clean, created_root.uri)

    assert root_with_files is not None
    assert root_with_files.uri == created_root.uri # Check URI
    assert len(root_with_files.files) == 0
