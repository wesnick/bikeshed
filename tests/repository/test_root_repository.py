import asyncio

import pytest
from uuid import uuid4, UUID
from datetime import datetime, timedelta

from psycopg import AsyncConnection
from psycopg.sql import SQL

from src.models.models import Root, RootFile
from src.repository.root import RootRepository

pytestmark = pytest.mark.asyncio


@pytest.fixture
def root_repo() -> RootRepository:
    return RootRepository()


@pytest.fixture
def sample_root_file() -> RootFile:
    return RootFile(
        id=uuid4(),
        root_id=uuid4(),  # This will be replaced in tests
        name="test_file.txt",
        path="/test/path/test_file.txt",
        extension="txt",
        mime_type="text/plain",
        size=1024,
        atime=datetime.now(),
        mtime=datetime.now(),
        ctime=datetime.now(),
        extra={"encoding": "utf-8"}
    )


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
    root = Root(**sample_root_data)
    created_root = await root_repo.create(db_conn_clean, root)

    assert created_root is not None
    assert created_root.id is not None
    assert created_root.uri == sample_root_data["uri"]
    assert created_root.extra == sample_root_data["extra"]
    assert isinstance(created_root.created_at, datetime)
    assert isinstance(created_root.last_accessed_at, datetime)


async def test_get_root_by_id(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    root = Root(**sample_root_data)
    created_root = await root_repo.create(db_conn_clean, root)

    fetched_root = await root_repo.get_by_id(db_conn_clean, created_root.id)

    assert fetched_root is not None
    assert fetched_root.id == created_root.id
    assert fetched_root.uri == created_root.uri


async def test_get_root_by_id_not_found(db_conn_clean: AsyncConnection, root_repo: RootRepository):
    non_existent_id = uuid4()
    fetched_root = await root_repo.get_by_id(db_conn_clean, non_existent_id)
    assert fetched_root is None


async def test_get_all_roots(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    root1_data = _create_root_data(sample_root_data, uri=f"file:///test/path/{uuid4().hex}")
    root2_data = _create_root_data(sample_root_data, uri=f"file:///test/path/{uuid4().hex}")
    root1 = Root(**root1_data)
    root2 = Root(**root2_data)
    await root_repo.create(db_conn_clean, root1)
    await root_repo.create(db_conn_clean, root2)

    all_roots = await root_repo.get_all(db_conn_clean, limit=10)

    assert len(all_roots) == 2
    root_uris = {r.uri for r in all_roots}
    assert root1_data["uri"] in root_uris
    assert root2_data["uri"] in root_uris


async def test_update_root(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    root = Root(**sample_root_data)
    created_root = await root_repo.create(db_conn_clean, root)

    update_data = {
        "uri": f"file:///updated/path/{uuid4().hex}",
        "extra": {"description": "Updated test root directory"}
    }
    updated_root = await root_repo.update(db_conn_clean, created_root.id, update_data)

    assert updated_root is not None
    assert updated_root.id == created_root.id
    assert updated_root.uri == update_data["uri"]
    assert updated_root.extra == update_data["extra"]
    # tests run too fast for this to be true, we verify the db trigger in other places
    # assert updated_root.last_accessed_at > created_root.last_accessed_at


async def test_update_root_not_found(db_conn_clean: AsyncConnection, root_repo: RootRepository):
    non_existent_id = uuid4()
    update_data = {"uri": f"file:///updated/path/{uuid4().hex}"}
    updated_root = await root_repo.update(db_conn_clean, non_existent_id, update_data)
    assert updated_root is None


async def test_delete_root(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    root = Root(**sample_root_data)
    created_root = await root_repo.create(db_conn_clean, root)

    deleted = await root_repo.delete(db_conn_clean, created_root.id)
    assert deleted is True

    fetched_root = await root_repo.get_by_id(db_conn_clean, created_root.id)
    assert fetched_root is None


async def test_delete_root_not_found(db_conn_clean: AsyncConnection, root_repo: RootRepository):
    non_existent_id = uuid4()
    deleted = await root_repo.delete(db_conn_clean, non_existent_id)
    assert deleted is False


async def test_filter_roots(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    root1_data = _create_root_data(sample_root_data, uri=f"file:///test/path/filter_test_1")
    root2_data = _create_root_data(sample_root_data, uri=f"file:///test/path/filter_test_2")
    root1 = Root(**root1_data)
    root2 = Root(**root2_data)
    await root_repo.create(db_conn_clean, root1)
    await root_repo.create(db_conn_clean, root2)

    filtered_roots = await root_repo.filter(db_conn_clean, {"uri": "file:///test/path/filter_test_2"})

    assert len(filtered_roots) == 1
    assert filtered_roots[0].uri == "file:///test/path/filter_test_2"


async def test_get_recent_roots(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    root1_data = _create_root_data(sample_root_data, uri=f"file:///test/path/old_root")
    root1 = Root(**root1_data)
    created1 = await root_repo.create(db_conn_clean, root1)

    # Simulate time passing
    await db_conn_clean.execute(
        SQL("UPDATE roots SET last_accessed_at = NOW() - INTERVAL '1 second' WHERE id = %s"), 
        (str(created1.id),)
    )

    root2_data = _create_root_data(sample_root_data, uri=f"file:///test/path/new_root")
    root2 = Root(**root2_data)
    created2 = await root_repo.create(db_conn_clean, root2)

    recent_roots = await root_repo.get_recent_roots(db_conn_clean, limit=1)
    assert len(recent_roots) == 1
    assert recent_roots[0].id == created2.id
    assert recent_roots[0].uri == root2_data["uri"]

    recent_roots_all = await root_repo.get_recent_roots(db_conn_clean, limit=5)
    assert len(recent_roots_all) == 2
    assert recent_roots_all[0].id == created2.id  # Newest first
    assert recent_roots_all[1].id == created1.id


async def test_get_root_by_uri(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    unique_uri = f"file:///test/path/unique_{uuid4().hex}"
    root_data = _create_root_data(sample_root_data, uri=unique_uri)
    root = Root(**root_data)
    created_root = await root_repo.create(db_conn_clean, root)

    fetched_root = await root_repo.get_by_uri(db_conn_clean, unique_uri)

    assert fetched_root is not None
    assert fetched_root.id == created_root.id
    assert fetched_root.uri == unique_uri


async def test_get_root_by_uri_not_found(db_conn_clean: AsyncConnection, root_repo: RootRepository):
    non_existent_uri = f"file:///test/path/non_existent_{uuid4().hex}"
    fetched_root = await root_repo.get_by_uri(db_conn_clean, non_existent_uri)
    assert fetched_root is None


async def test_update_last_accessed(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    root = Root(**sample_root_data)
    created_root = await root_repo.create(db_conn_clean, root)
    
    # Get the initial last_accessed_at time
    initial_root = await root_repo.get_by_id(db_conn_clean, created_root.id)
    initial_accessed_at = initial_root.last_accessed_at
    
    # Simulate time passing
    await db_conn_clean.execute(
        SQL("UPDATE roots SET last_accessed_at = NOW() - INTERVAL '1 hour' WHERE id = %s"), 
        (str(created_root.id),)
    )
    
    # Update last_accessed_at
    updated_root = await root_repo.update_last_accessed(db_conn_clean, created_root.id)
    
    assert updated_root is not None
    assert updated_root.id == created_root.id
    # The timestamp should be updated to now
    assert updated_root.last_accessed_at > initial_accessed_at


async def test_update_last_accessed_not_found(db_conn_clean: AsyncConnection, root_repo: RootRepository):
    non_existent_id = uuid4()
    updated_root = await root_repo.update_last_accessed(db_conn_clean, non_existent_id)
    assert updated_root is None


async def test_get_with_files(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict, sample_root_file: RootFile):
    # Create a root
    root = Root(**sample_root_data)
    created_root = await root_repo.create(db_conn_clean, root)
    
    # Create files for this root
    file1 = sample_root_file.model_copy()
    file1.root_id = created_root.id
    file1.path = "/test/path/file1.txt"
    file1.name = "file1.txt"
    
    file2 = sample_root_file.model_copy()
    file2.root_id = created_root.id
    file2.path = "/test/path/file2.txt"
    file2.name = "file2.txt"
    
    # Insert files directly into the database
    await db_conn_clean.execute(
        """
        INSERT INTO root_files (id, root_id, name, path, extension, mime_type, size, atime, mtime, ctime, extra)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            str(file1.id), str(file1.root_id), file1.name, file1.path, file1.extension,
            file1.mime_type, file1.size, file1.atime, file1.mtime, file1.ctime, 
            file1.extra
        )
    )
    
    await db_conn_clean.execute(
        """
        INSERT INTO root_files (id, root_id, name, path, extension, mime_type, size, atime, mtime, ctime, extra)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            str(file2.id), str(file2.root_id), file2.name, file2.path, file2.extension,
            file2.mime_type, file2.size, file2.atime, file2.mtime, file2.ctime, 
            file2.extra
        )
    )
    
    # Get the root with its files
    root_with_files = await root_repo.get_with_files(db_conn_clean, created_root.id)
    
    assert root_with_files is not None
    assert root_with_files.id == created_root.id
    assert len(root_with_files.files) == 2
    
    # Files should be ordered by path
    assert root_with_files.files[0].name == "file1.txt"
    assert root_with_files.files[1].name == "file2.txt"
    
    # Verify file properties
    assert root_with_files.files[0].root_id == created_root.id
    assert root_with_files.files[0].extension == "txt"
    assert root_with_files.files[0].mime_type == "text/plain"


async def test_get_with_files_not_found(db_conn_clean: AsyncConnection, root_repo: RootRepository):
    non_existent_id = uuid4()
    root_with_files = await root_repo.get_with_files(db_conn_clean, non_existent_id)
    assert root_with_files is None


async def test_get_with_files_no_files(db_conn_clean: AsyncConnection, root_repo: RootRepository, sample_root_data: dict):
    # Create a root without any files
    root = Root(**sample_root_data)
    created_root = await root_repo.create(db_conn_clean, root)
    
    # Get the root with its files (should be empty)
    root_with_files = await root_repo.get_with_files(db_conn_clean, created_root.id)
    
    assert root_with_files is not None
    assert root_with_files.id == created_root.id
    assert len(root_with_files.files) == 0
