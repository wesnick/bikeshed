import pytest
from uuid import uuid4
from datetime import datetime

from psycopg import AsyncConnection
from psycopg.sql import SQL

from src.core.models import Quickie, QuickieStatus
from src.components.quickie.repository import QuickieRepository

pytestmark = pytest.mark.asyncio


@pytest.fixture
def quickie_repo() -> QuickieRepository:
    return QuickieRepository()


@pytest.fixture
def sample_quickie_data() -> dict:
    return {
        "template_name": "test_template",
        "prompt_text": "This is a test prompt",
        "prompt_hash": "abc123hash",
        "input_params": {"param1": "value1", "param2": 42},
        "tools": ["tool1", "tool2"],
        "model": "gpt-4",
        "metadata": {"category": "test"}
    }


def _create_quickie_data(base_data: dict, **kwargs) -> dict:
    """Helper to create unique quickie data for tests."""
    data = base_data.copy()
    data.update(kwargs)
    return data


async def test_create_quickie(db_conn_clean: AsyncConnection, quickie_repo: QuickieRepository, sample_quickie_data: dict):
    quickie = Quickie(**sample_quickie_data)
    created_quickie = await quickie_repo.create(db_conn_clean, quickie)

    assert created_quickie is not None
    assert created_quickie.id is not None
    assert created_quickie.template_name == sample_quickie_data["template_name"]
    assert created_quickie.prompt_text == sample_quickie_data["prompt_text"]
    assert created_quickie.prompt_hash == sample_quickie_data["prompt_hash"]
    assert created_quickie.input_params == sample_quickie_data["input_params"]
    assert created_quickie.tools == sample_quickie_data["tools"]
    assert created_quickie.model == sample_quickie_data["model"]
    assert created_quickie.status == QuickieStatus.PENDING
    assert created_quickie.metadata == sample_quickie_data["metadata"]
    assert isinstance(created_quickie.created_at, datetime)


async def test_get_quickie_by_id(db_conn_clean: AsyncConnection, quickie_repo: QuickieRepository, sample_quickie_data: dict):
    quickie = Quickie(**sample_quickie_data)
    created_quickie = await quickie_repo.create(db_conn_clean, quickie)

    fetched_quickie = await quickie_repo.get_by_id(db_conn_clean, created_quickie.id)

    assert fetched_quickie is not None
    assert fetched_quickie.id == created_quickie.id
    assert fetched_quickie.template_name == created_quickie.template_name
    assert fetched_quickie.prompt_hash == created_quickie.prompt_hash


async def test_get_quickie_by_id_not_found(db_conn_clean: AsyncConnection, quickie_repo: QuickieRepository):
    non_existent_id = uuid4()
    fetched_quickie = await quickie_repo.get_by_id(db_conn_clean, non_existent_id)
    assert fetched_quickie is None


async def test_get_all_quickies(db_conn_clean: AsyncConnection, quickie_repo: QuickieRepository, sample_quickie_data: dict):
    quickie1_data = _create_quickie_data(sample_quickie_data, template_name="template1", prompt_hash="hash1")
    quickie2_data = _create_quickie_data(sample_quickie_data, template_name="template2", prompt_hash="hash2")
    quickie1 = Quickie(**quickie1_data)
    quickie2 = Quickie(**quickie2_data)
    await quickie_repo.create(db_conn_clean, quickie1)
    await quickie_repo.create(db_conn_clean, quickie2)

    all_quickies = await quickie_repo.get_all(db_conn_clean, limit=10)

    assert len(all_quickies) == 2
    template_names = {q.template_name for q in all_quickies}
    assert "template1" in template_names
    assert "template2" in template_names


async def test_update_quickie(db_conn_clean: AsyncConnection, quickie_repo: QuickieRepository, sample_quickie_data: dict):
    quickie = Quickie(**sample_quickie_data)
    created_quickie = await quickie_repo.create(db_conn_clean, quickie)

    update_data = {
        "output": {"result": "This is the generated output"},
        "status": QuickieStatus.COMPLETE,
        "metadata": {"runtime_ms": 1500, "tokens": 250}
    }
    updated_quickie = await quickie_repo.update(db_conn_clean, created_quickie.id, update_data)

    assert updated_quickie is not None
    assert updated_quickie.id == created_quickie.id
    assert updated_quickie.template_name == created_quickie.template_name
    assert updated_quickie.status == QuickieStatus.COMPLETE
    assert updated_quickie.output == {"result": "This is the generated output"}
    assert updated_quickie.metadata == {"runtime_ms": 1500, "tokens": 250}


async def test_update_quickie_not_found(db_conn_clean: AsyncConnection, quickie_repo: QuickieRepository):
    non_existent_id = uuid4()
    update_data = {"status": QuickieStatus.ERROR, "error": "Test error"}
    updated_quickie = await quickie_repo.update(db_conn_clean, non_existent_id, update_data)
    assert updated_quickie is None


async def test_delete_quickie(db_conn_clean: AsyncConnection, quickie_repo: QuickieRepository, sample_quickie_data: dict):
    quickie = Quickie(**sample_quickie_data)
    created_quickie = await quickie_repo.create(db_conn_clean, quickie)

    deleted = await quickie_repo.delete(db_conn_clean, created_quickie.id)
    assert deleted is True

    fetched_quickie = await quickie_repo.get_by_id(db_conn_clean, created_quickie.id)
    assert fetched_quickie is None


async def test_delete_quickie_not_found(db_conn_clean: AsyncConnection, quickie_repo: QuickieRepository):
    non_existent_id = uuid4()
    deleted = await quickie_repo.delete(db_conn_clean, non_existent_id)
    assert deleted is False


async def test_get_by_template_name(db_conn_clean: AsyncConnection, quickie_repo: QuickieRepository, sample_quickie_data: dict):
    template_name = "unique_template_name"
    quickie1_data = _create_quickie_data(sample_quickie_data, template_name=template_name, prompt_hash="hash1")
    quickie2_data = _create_quickie_data(sample_quickie_data, template_name=template_name, prompt_hash="hash2")
    quickie3_data = _create_quickie_data(sample_quickie_data, template_name="different_template", prompt_hash="hash3")
    
    await quickie_repo.create(db_conn_clean, Quickie(**quickie1_data))
    await quickie_repo.create(db_conn_clean, Quickie(**quickie2_data))
    await quickie_repo.create(db_conn_clean, Quickie(**quickie3_data))
    
    results = await quickie_repo.get_by_template_name(db_conn_clean, template_name)
    
    assert len(results) == 2
    assert all(q.template_name == template_name for q in results)


async def test_get_by_prompt_hash(db_conn_clean: AsyncConnection, quickie_repo: QuickieRepository, sample_quickie_data: dict):
    unique_hash = "unique_hash_value"
    quickie_data = _create_quickie_data(sample_quickie_data, prompt_hash=unique_hash)
    quickie = Quickie(**quickie_data)
    created_quickie = await quickie_repo.create(db_conn_clean, quickie)
    
    fetched_quickie = await quickie_repo.get_by_prompt_hash(db_conn_clean, unique_hash)
    
    assert fetched_quickie is not None
    assert fetched_quickie.id == created_quickie.id
    assert fetched_quickie.prompt_hash == unique_hash


async def test_update_status(db_conn_clean: AsyncConnection, quickie_repo: QuickieRepository, sample_quickie_data: dict):
    quickie = Quickie(**sample_quickie_data)
    created_quickie = await quickie_repo.create(db_conn_clean, quickie)
    
    # Update to ERROR status with error message
    updated_quickie = await quickie_repo.update_status(
        db_conn_clean, 
        created_quickie.id, 
        QuickieStatus.ERROR, 
        "Test error message"
    )
    
    assert updated_quickie is not None
    assert updated_quickie.status == QuickieStatus.ERROR
    assert updated_quickie.error == "Test error message"
    
    # Update back to PENDING without error message
    updated_quickie = await quickie_repo.update_status(
        db_conn_clean,
        created_quickie.id,
        QuickieStatus.PENDING
    )
    
    assert updated_quickie.status == QuickieStatus.PENDING
    # Error message should remain from previous update
    assert updated_quickie.error == "Test error message"


async def test_update_output(db_conn_clean: AsyncConnection, quickie_repo: QuickieRepository, sample_quickie_data: dict):
    quickie = Quickie(**sample_quickie_data)
    created_quickie = await quickie_repo.create(db_conn_clean, quickie)
    
    output_data = {"text": "Generated response", "confidence": 0.95}
    metadata = {"tokens": 150, "model_version": "2023-05"}
    
    updated_quickie = await quickie_repo.update_output(
        db_conn_clean,
        created_quickie.id,
        output_data,
        metadata
    )
    
    assert updated_quickie is not None
    assert updated_quickie.output == output_data
    assert updated_quickie.metadata == metadata
    assert updated_quickie.status == QuickieStatus.COMPLETE


async def test_get_recent_by_status(db_conn_clean: AsyncConnection, quickie_repo: QuickieRepository, sample_quickie_data: dict):
    # Create quickies with different statuses
    pending_data = _create_quickie_data(sample_quickie_data, prompt_hash="pending1")
    complete_data1 = _create_quickie_data(sample_quickie_data, prompt_hash="complete1")
    complete_data2 = _create_quickie_data(sample_quickie_data, prompt_hash="complete2")
    error_data = _create_quickie_data(sample_quickie_data, prompt_hash="error1")
    
    pending_quickie = await quickie_repo.create(db_conn_clean, Quickie(**pending_data))
    complete_quickie1 = await quickie_repo.create(db_conn_clean, Quickie(**complete_data1))
    complete_quickie2 = await quickie_repo.create(db_conn_clean, Quickie(**complete_data2))
    error_quickie = await quickie_repo.create(db_conn_clean, Quickie(**error_data))
    
    # Update statuses
    await quickie_repo.update_status(db_conn_clean, complete_quickie1.id, QuickieStatus.COMPLETE)
    await quickie_repo.update_status(db_conn_clean, complete_quickie2.id, QuickieStatus.COMPLETE)
    await quickie_repo.update_status(db_conn_clean, error_quickie.id, QuickieStatus.ERROR, "Test error")
    
    # Get recent COMPLETE quickies
    complete_results = await quickie_repo.get_recent_by_status(db_conn_clean, QuickieStatus.COMPLETE, limit=5)
    assert len(complete_results) == 2
    assert all(q.status == QuickieStatus.COMPLETE for q in complete_results)
    
    # Get recent PENDING quickies
    pending_results = await quickie_repo.get_recent_by_status(db_conn_clean, QuickieStatus.PENDING, limit=5)
    assert len(pending_results) == 1
    assert pending_results[0].id == pending_quickie.id
    
    # Get recent ERROR quickies
    error_results = await quickie_repo.get_recent_by_status(db_conn_clean, QuickieStatus.ERROR, limit=5)
    assert len(error_results) == 1
    assert error_results[0].id == error_quickie.id
    assert error_results[0].error == "Test error"
