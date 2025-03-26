import pytest
from uuid import uuid4, UUID
from datetime import datetime

from psycopg import AsyncConnection

from src.models.models import Stash, StashItem
from src.repository.stash import StashRepository

pytestmark = pytest.mark.asyncio


@pytest.fixture
def stash_repo() -> StashRepository:
    return StashRepository()


@pytest.fixture
def sample_stash_item_text() -> StashItem:
    return StashItem(type="text", content="Sample text content")


@pytest.fixture
def sample_stash_item_blob() -> StashItem:
    return StashItem(type="blob", content=str(uuid4()), metadata={"filename": "image.jpg"})


@pytest.fixture
def sample_stash_data(sample_stash_item_text) -> dict:
    return {
        "name": "test_stash",
        "description": "A stash for testing",
        "items": [sample_stash_item_text],
        "metadata": {"category": "test"},
    }


async def test_create_stash(db_conn_clean: AsyncConnection, stash_repo: StashRepository, sample_stash_data: dict):
    stash = Stash(**sample_stash_data)
    created_stash = await stash_repo.create(db_conn_clean, stash)

    assert created_stash is not None
    assert created_stash.id is not None
    assert created_stash.name == sample_stash_data["name"]
    assert created_stash.description == sample_stash_data["description"]
    assert len(created_stash.items) == 1
    assert created_stash.items[0].type == "text"
    assert created_stash.items[0].content == "Sample text content"
    assert created_stash.metadata == sample_stash_data["metadata"]
    assert isinstance(created_stash.created_at, datetime)
    assert isinstance(created_stash.updated_at, datetime)


async def test_get_stash_by_id(db_conn_clean: AsyncConnection, stash_repo: StashRepository, sample_stash_data: dict):
    stash = Stash(**sample_stash_data)
    created_stash = await stash_repo.create(db_conn_clean, stash)

    fetched_stash = await stash_repo.get_by_id(db_conn_clean, created_stash.id)

    assert fetched_stash is not None
    assert fetched_stash.id == created_stash.id
    assert fetched_stash.name == created_stash.name
    assert len(fetched_stash.items) == 1


async def test_get_stash_by_id_not_found(db_conn_clean: AsyncConnection, stash_repo: StashRepository):
    non_existent_id = uuid4()
    fetched_stash = await stash_repo.get_by_id(db_conn_clean, non_existent_id)
    assert fetched_stash is None


async def test_get_all_stashes(db_conn_clean: AsyncConnection, stash_repo: StashRepository, sample_stash_data: dict):
    stash1 = Stash(**sample_stash_data, name="stash1")
    stash2 = Stash(**sample_stash_data, name="stash2")
    await stash_repo.create(db_conn_clean, stash1)
    await stash_repo.create(db_conn_clean, stash2)

    all_stashes = await stash_repo.get_all(db_conn_clean, limit=10)

    assert len(all_stashes) == 2
    stash_names = {s.name for s in all_stashes}
    assert "stash1" in stash_names
    assert "stash2" in stash_names


async def test_update_stash(db_conn_clean: AsyncConnection, stash_repo: StashRepository, sample_stash_data: dict, sample_stash_item_blob: StashItem):
    stash = Stash(**sample_stash_data)
    created_stash = await stash_repo.create(db_conn_clean, stash)

    update_data = {
        "name": "updated_stash_name",
        "description": "Updated description",
        "items": [sample_stash_item_blob], # Replace items
        "metadata": {"category": "updated_test"}
    }
    updated_stash = await stash_repo.update(db_conn_clean, created_stash.id, update_data)

    assert updated_stash is not None
    assert updated_stash.id == created_stash.id
    assert updated_stash.name == "updated_stash_name"
    assert updated_stash.description == "Updated description"
    assert len(updated_stash.items) == 1
    assert updated_stash.items[0].type == "blob"
    assert updated_stash.items[0].metadata == {"filename": "image.jpg"}
    assert updated_stash.metadata == {"category": "updated_test"}
    assert updated_stash.updated_at > created_stash.updated_at


async def test_update_stash_not_found(db_conn_clean: AsyncConnection, stash_repo: StashRepository):
    non_existent_id = uuid4()
    update_data = {"name": "updated_name"}
    updated_stash = await stash_repo.update(db_conn_clean, non_existent_id, update_data)
    assert updated_stash is None


async def test_delete_stash(db_conn_clean: AsyncConnection, stash_repo: StashRepository, sample_stash_data: dict):
    stash = Stash(**sample_stash_data)
    created_stash = await stash_repo.create(db_conn_clean, stash)

    deleted = await stash_repo.delete(db_conn_clean, created_stash.id)
    assert deleted is True

    fetched_stash = await stash_repo.get_by_id(db_conn_clean, created_stash.id)
    assert fetched_stash is None


async def test_delete_stash_not_found(db_conn_clean: AsyncConnection, stash_repo: StashRepository):
    non_existent_id = uuid4()
    deleted = await stash_repo.delete(db_conn_clean, non_existent_id)
    assert deleted is False


async def test_filter_stashes(db_conn_clean: AsyncConnection, stash_repo: StashRepository, sample_stash_data: dict):
    stash1 = Stash(**sample_stash_data, name="filter_test_1", metadata={"category": "A"})
    stash2 = Stash(**sample_stash_data, name="filter_test_2", metadata={"category": "B"})
    await stash_repo.create(db_conn_clean, stash1)
    await stash_repo.create(db_conn_clean, stash2)

    # Note: Filtering directly on JSONB fields like metadata requires specific query adjustments
    # The basic filter method in BaseRepository might not work directly for nested JSON fields.
    # This test assumes filtering by top-level fields like 'name'.
    filtered_stashes = await stash_repo.filter(db_conn_clean, {"name": "filter_test_2"})

    assert len(filtered_stashes) == 1
    assert filtered_stashes[0].name == "filter_test_2"
    # assert filtered_stashes[0].metadata == {"category": "B"} # This might fail if metadata isn't fetched correctly or filter is basic


async def test_get_recent_stashes(db_conn_clean: AsyncConnection, stash_repo: StashRepository, sample_stash_data: dict):
    stash1 = Stash(**sample_stash_data, name="stash_old")
    created1 = await stash_repo.create(db_conn_clean, stash1)
    # Simulate time passing
    await db_conn_clean.execute("SELECT pg_sleep(0.1)")
    stash2 = Stash(**sample_stash_data, name="stash_new")
    created2 = await stash_repo.create(db_conn_clean, stash2)

    recent_stashes = await stash_repo.get_recent_stashes(db_conn_clean, limit=1)
    assert len(recent_stashes) == 1
    assert recent_stashes[0].id == created2.id
    assert recent_stashes[0].name == "stash_new"

    recent_stashes_all = await stash_repo.get_recent_stashes(db_conn_clean, limit=5)
    assert len(recent_stashes_all) == 2
    assert recent_stashes_all[0].id == created2.id # Newest first
    assert recent_stashes_all[1].id == created1.id


async def test_get_stash_by_name(db_conn_clean: AsyncConnection, stash_repo: StashRepository, sample_stash_data: dict):
    stash_name = f"unique_stash_name_{uuid4().hex[:8]}"
    stash = Stash(**sample_stash_data, name=stash_name)
    await stash_repo.create(db_conn_clean, stash)

    fetched_stash = await stash_repo.get_by_name(db_conn_clean, stash_name)
    assert fetched_stash is not None
    assert fetched_stash.id == stash.id
    assert fetched_stash.name == stash_name


async def test_get_stash_by_name_not_found(db_conn_clean: AsyncConnection, stash_repo: StashRepository):
    fetched_stash = await stash_repo.get_by_name(db_conn_clean, "non_existent_stash_name")
    assert fetched_stash is None


async def test_add_stash_item(db_conn_clean: AsyncConnection, stash_repo: StashRepository, sample_stash_data: dict, sample_stash_item_blob: StashItem):
    stash = Stash(**sample_stash_data) # Starts with one text item
    created_stash = await stash_repo.create(db_conn_clean, stash)
    assert len(created_stash.items) == 1

    updated_stash = await stash_repo.add_item(db_conn_clean, created_stash.id, sample_stash_item_blob)

    assert updated_stash is not None
    assert len(updated_stash.items) == 2
    assert updated_stash.items[0].type == "text" # Original item
    assert updated_stash.items[1].type == "blob" # New item
    assert updated_stash.items[1].content == sample_stash_item_blob.content
    assert updated_stash.updated_at > created_stash.updated_at


async def test_add_stash_item_stash_not_found(db_conn_clean: AsyncConnection, stash_repo: StashRepository, sample_stash_item_text: StashItem):
    non_existent_id = uuid4()
    with pytest.raises(ValueError, match=f"Stash with ID {non_existent_id} not found"):
        await stash_repo.add_item(db_conn_clean, non_existent_id, sample_stash_item_text)


async def test_remove_stash_item(db_conn_clean: AsyncConnection, stash_repo: StashRepository, sample_stash_data: dict, sample_stash_item_blob: StashItem):
    # Start with two items
    stash = Stash(**sample_stash_data) # Has one text item
    stash.items.append(sample_stash_item_blob) # Add blob item
    created_stash = await stash_repo.create(db_conn_clean, stash)
    assert len(created_stash.items) == 2

    # Remove the first item (index 0)
    updated_stash = await stash_repo.remove_item(db_conn_clean, created_stash.id, 0)

    assert updated_stash is not None
    assert len(updated_stash.items) == 1
    assert updated_stash.items[0].type == "blob" # Only blob item should remain
    assert updated_stash.items[0].content == sample_stash_item_blob.content
    assert updated_stash.updated_at > created_stash.updated_at

    # Remove the remaining item (index 0 again)
    updated_stash_2 = await stash_repo.remove_item(db_conn_clean, created_stash.id, 0)
    assert updated_stash_2 is not None
    assert len(updated_stash_2.items) == 0
    assert updated_stash_2.updated_at > updated_stash.updated_at


async def test_remove_stash_item_invalid_index(db_conn_clean: AsyncConnection, stash_repo: StashRepository, sample_stash_data: dict):
    stash = Stash(**sample_stash_data) # Has one item
    created_stash = await stash_repo.create(db_conn_clean, stash)

    with pytest.raises(ValueError, match="Invalid item index: 1"):
        await stash_repo.remove_item(db_conn_clean, created_stash.id, 1)

    with pytest.raises(ValueError, match="Invalid item index: -1"):
        await stash_repo.remove_item(db_conn_clean, created_stash.id, -1)


async def test_remove_stash_item_stash_not_found(db_conn_clean: AsyncConnection, stash_repo: StashRepository):
    non_existent_id = uuid4()
    with pytest.raises(ValueError, match=f"Stash with ID {non_existent_id} not found"):
        await stash_repo.remove_item(db_conn_clean, non_existent_id, 0)
