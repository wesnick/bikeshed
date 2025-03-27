import asyncio

import pytest
from uuid import uuid4, UUID
from datetime import datetime, timedelta

from psycopg import AsyncConnection
from psycopg.sql import SQL

from src.models.models import Message, MessageStatus
from src.repository.message import MessageRepository

pytestmark = pytest.mark.asyncio


@pytest.fixture
def message_repo() -> MessageRepository:
    return MessageRepository()


@pytest.fixture
def sample_session_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_message_data(sample_session_id) -> dict:
    return {
        "session_id": sample_session_id,
        "role": "user",
        "text": "Sample message text",
        "status": MessageStatus.CREATED,
        "mime_type": "text/plain",
    }


def _create_message_data(base_data: dict, **kwargs) -> dict:
    """Helper to create unique message data for tests."""
    data = base_data.copy()
    data.update(kwargs)
    return data


async def test_create_message(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict):
    message = Message(**sample_message_data)
    created_message = await message_repo.create(db_conn_clean, message)

    assert created_message is not None
    assert created_message.id is not None
    assert created_message.session_id == sample_message_data["session_id"]
    assert created_message.role == sample_message_data["role"]
    assert created_message.text == sample_message_data["text"]
    assert created_message.status == MessageStatus.CREATED
    assert created_message.mime_type == "text/plain"
    assert isinstance(created_message.timestamp, datetime)


async def test_get_message_by_id(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict):
    message = Message(**sample_message_data)
    created_message = await message_repo.create(db_conn_clean, message)

    fetched_message = await message_repo.get_by_id(db_conn_clean, created_message.id)

    assert fetched_message is not None
    assert fetched_message.id == created_message.id
    assert fetched_message.text == created_message.text


async def test_get_message_by_id_not_found(db_conn_clean: AsyncConnection, message_repo: MessageRepository):
    non_existent_id = uuid4()
    fetched_message = await message_repo.get_by_id(db_conn_clean, non_existent_id)
    assert fetched_message is None


async def test_get_all_messages(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict):
    message1_data = _create_message_data(sample_message_data, text="message1")
    message2_data = _create_message_data(sample_message_data, text="message2")
    message1 = Message(**message1_data)
    message2 = Message(**message2_data)
    await message_repo.create(db_conn_clean, message1)
    await message_repo.create(db_conn_clean, message2)

    all_messages = await message_repo.get_all(db_conn_clean, limit=10)

    assert len(all_messages) == 2
    message_texts = {m.text for m in all_messages}
    assert "message1" in message_texts
    assert "message2" in message_texts


async def test_update_message(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict):
    message = Message(**sample_message_data)
    created_message = await message_repo.create(db_conn_clean, message)

    update_data = {
        "text": "updated_message_text",
        "status": MessageStatus.DELIVERED,
        "extra": {"key": "value"}
    }
    updated_message = await message_repo.update(db_conn_clean, created_message.id, update_data)

    assert updated_message is not None
    assert updated_message.id == created_message.id
    assert updated_message.text == "updated_message_text"
    assert updated_message.status == MessageStatus.DELIVERED
    assert updated_message.extra == {"key": "value"}


async def test_update_message_not_found(db_conn_clean: AsyncConnection, message_repo: MessageRepository):
    non_existent_id = uuid4()
    update_data = {"text": "updated_text"}
    updated_message = await message_repo.update(db_conn_clean, non_existent_id, update_data)
    assert updated_message is None


async def test_delete_message(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict):
    message = Message(**sample_message_data)
    created_message = await message_repo.create(db_conn_clean, message)

    deleted = await message_repo.delete(db_conn_clean, created_message.id)
    assert deleted is True

    fetched_message = await message_repo.get_by_id(db_conn_clean, created_message.id)
    assert fetched_message is None


async def test_delete_message_not_found(db_conn_clean: AsyncConnection, message_repo: MessageRepository):
    non_existent_id = uuid4()
    deleted = await message_repo.delete(db_conn_clean, non_existent_id)
    assert deleted is False


async def test_filter_messages(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict):
    message1_data = _create_message_data(sample_message_data, role="user", text="filter_test_1")
    message2_data = _create_message_data(sample_message_data, role="assistant", text="filter_test_2", model="gpt-4")
    message1 = Message(**message1_data)
    message2 = Message(**message2_data)
    await message_repo.create(db_conn_clean, message1)
    await message_repo.create(db_conn_clean, message2)

    filtered_messages = await message_repo.filter(db_conn_clean, {"role": "assistant"})

    assert len(filtered_messages) == 1
    assert filtered_messages[0].role == "assistant"
    assert filtered_messages[0].text == "filter_test_2"
    assert filtered_messages[0].model == "gpt-4"


async def test_get_by_session(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict):
    # Create two sessions
    session_id_1 = sample_message_data["session_id"]
    session_id_2 = uuid4()
    
    # Create messages for session 1
    message1_data = _create_message_data(sample_message_data, text="session1_message1")
    message2_data = _create_message_data(sample_message_data, text="session1_message2")
    message1 = Message(**message1_data)
    message2 = Message(**message2_data)
    await message_repo.create(db_conn_clean, message1)
    await message_repo.create(db_conn_clean, message2)
    
    # Create message for session 2
    message3_data = _create_message_data(sample_message_data, session_id=session_id_2, text="session2_message")
    message3 = Message(**message3_data)
    await message_repo.create(db_conn_clean, message3)
    
    # Get messages for session 1
    session1_messages = await message_repo.get_by_session(db_conn_clean, session_id_1)
    
    assert len(session1_messages) == 2
    message_texts = {m.text for m in session1_messages}
    assert "session1_message1" in message_texts
    assert "session1_message2" in message_texts
    assert "session2_message" not in message_texts
    
    # Get messages for session 2
    session2_messages = await message_repo.get_by_session(db_conn_clean, session_id_2)
    
    assert len(session2_messages) == 1
    assert session2_messages[0].text == "session2_message"


async def test_get_thread(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict):
    # Create a parent message
    parent_data = _create_message_data(sample_message_data, text="parent_message")
    parent = Message(**parent_data)
    created_parent = await message_repo.create(db_conn_clean, parent)
    
    # Create child messages
    child1_data = _create_message_data(sample_message_data, 
                                      text="child_message_1", 
                                      parent_id=created_parent.id)
    child2_data = _create_message_data(sample_message_data, 
                                      text="child_message_2", 
                                      parent_id=created_parent.id)
    
    child1 = Message(**child1_data)
    child2 = Message(**child2_data)
    await message_repo.create(db_conn_clean, child1)
    await message_repo.create(db_conn_clean, child2)
    
    # Get the thread
    thread = await message_repo.get_thread(db_conn_clean, created_parent.id)
    
    assert len(thread) == 3
    assert thread[0].id == created_parent.id
    assert thread[0].text == "parent_message"
    
    # Check that children are included
    child_texts = {thread[1].text, thread[2].text}
    assert "child_message_1" in child_texts
    assert "child_message_2" in child_texts


async def test_get_thread_not_found(db_conn_clean: AsyncConnection, message_repo: MessageRepository):
    non_existent_id = uuid4()
    thread = await message_repo.get_thread(db_conn_clean, non_existent_id)
    assert thread == []


async def test_message_timestamp_ordering(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict):
    # Create messages with different timestamps
    message1_data = _create_message_data(sample_message_data, text="older_message")
    message1 = Message(**message1_data)
    created_message1 = await message_repo.create(db_conn_clean, message1)
    
    # Simulate time passing
    await db_conn_clean.execute(
        SQL("UPDATE messages SET timestamp = NOW() - INTERVAL '1 minute' WHERE id = %s"), 
        (str(created_message1.id),)
    )
    
    message2_data = _create_message_data(sample_message_data, text="newer_message")
    message2 = Message(**message2_data)
    created_message2 = await message_repo.create(db_conn_clean, message2)
    
    # Get messages by session, should be ordered by timestamp
    session_messages = await message_repo.get_by_session(db_conn_clean, sample_message_data["session_id"])
    
    assert len(session_messages) == 2
    assert session_messages[0].text == "older_message"
    assert session_messages[1].text == "newer_message"


async def test_create_message_with_model(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict):
    # Assistant messages require a model
    assistant_data = _create_message_data(sample_message_data, role="assistant", model="gpt-4", text="Assistant response")
    assistant_message = Message(**assistant_data)
    created_message = await message_repo.create(db_conn_clean, assistant_message)
    
    assert created_message is not None
    assert created_message.role == "assistant"
    assert created_message.model == "gpt-4"


async def test_create_assistant_message_without_model_fails(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict):
    # Assistant messages without model should fail validation
    assistant_data = _create_message_data(sample_message_data, role="assistant", model=None, text="Assistant response")
    
    with pytest.raises(ValueError, match="Model must be set for assistant messages"):
        Message(**assistant_data)


async def test_message_with_extra_data(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict):
    # Test with extra data
    extra_data = {"temperature": 0.7, "top_p": 1.0, "tokens": 150}
    message_data = _create_message_data(sample_message_data, extra=extra_data)
    message = Message(**message_data)
    created_message = await message_repo.create(db_conn_clean, message)
    
    fetched_message = await message_repo.get_by_id(db_conn_clean, created_message.id)
    assert fetched_message.extra == extra_data
