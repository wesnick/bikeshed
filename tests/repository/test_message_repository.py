import pytest
from uuid import uuid4
from datetime import datetime

from psycopg import AsyncConnection
from psycopg.sql import SQL

from src.core.models import Message, MessageStatus, Dialog, DialogStatus
from src.components.message.repository import MessageRepository
from src.components.dialog.repository import DialogRepository

pytestmark = pytest.mark.asyncio


@pytest.fixture
def message_repo() -> MessageRepository:
    return MessageRepository()


@pytest.fixture
def dialog_repo() -> DialogRepository:
    return DialogRepository()


@pytest.fixture
async def test_dialog(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository) -> Dialog:
    """Create a test dialog to use for message tests"""
    dialog = Dialog(
        description="Test dialog",
        status=DialogStatus.PENDING,
        current_state="start",
    )
    created_dialog = await dialog_repo.create(db_conn_clean, dialog)
    return created_dialog


@pytest.fixture
def sample_message_data(test_dialog) -> dict:
    return {
        "dialog_id": test_dialog.id,
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


async def test_create_message(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict, test_dialog: Dialog):
    message = Message(**sample_message_data)
    created_message = await message_repo.create(db_conn_clean, message)

    assert created_message is not None
    assert created_message.id is not None
    assert created_message.dialog_id == test_dialog.id
    assert created_message.role == sample_message_data["role"]
    assert created_message.text == sample_message_data["text"]
    assert created_message.status == MessageStatus.CREATED
    assert created_message.mime_type == "text/plain"
    assert isinstance(created_message.timestamp, datetime)


async def test_get_message_by_id(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict, test_dialog: Dialog):
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


async def test_get_all_messages(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict, test_dialog: Dialog):
    message1_data = _create_message_data(sample_message_data, text="message1")
    message2_data = _create_message_data(sample_message_data, text="message2")
    message1 = Message(**message1_data)
    message2 = Message(**message2_data)
    await message_repo.create(db_conn_clean, message1)
    await message_repo.create(db_conn_clean, message2)

    all_messages = await message_repo.get_all(db_conn_clean, limit=10)

    assert len(all_messages) >= 2  # There might be other messages from other tests
    message_texts = {m.text for m in all_messages}
    assert "message1" in message_texts
    assert "message2" in message_texts


async def test_update_message(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict, test_dialog: Dialog):
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


async def test_delete_message(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict, test_dialog: Dialog):
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


async def test_filter_messages(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict, test_dialog: Dialog):
    message1_data = _create_message_data(sample_message_data, role="user", text="filter_test_1")
    message2_data = _create_message_data(sample_message_data, role="assistant", text="filter_test_2", model="gpt-4")
    message1 = Message(**message1_data)
    message2 = Message(**message2_data)
    await message_repo.create(db_conn_clean, message1)
    await message_repo.create(db_conn_clean, message2)

    filtered_messages = await message_repo.filter(db_conn_clean, {"role": "assistant", "dialog_id": test_dialog.id})

    assert len(filtered_messages) == 1
    assert filtered_messages[0].role == "assistant"
    assert filtered_messages[0].text == "filter_test_2"
    assert filtered_messages[0].model == "gpt-4"


async def test_get_by_dialog(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict, test_dialog: Dialog, dialog_repo: DialogRepository):
    # Create a second dialog
    dialog2 = Dialog(
        description="Test dialog 2",
        status=DialogStatus.PENDING,
        current_state="start",
    )
    created_dialog2 = await dialog_repo.create(db_conn_clean, dialog2)

    # Create messages for dialog 1
    message1_data = _create_message_data(sample_message_data, text="dialog1_message1")
    message2_data = _create_message_data(sample_message_data, text="dialog1_message2")
    message1 = Message(**message1_data)
    message2 = Message(**message2_data)
    await message_repo.create(db_conn_clean, message1)
    await message_repo.create(db_conn_clean, message2)

    # Create message for dialog 2
    message3_data = _create_message_data(sample_message_data, dialog_id=created_dialog2.id, text="dialog2_message")
    message3 = Message(**message3_data)
    await message_repo.create(db_conn_clean, message3)

    # Get messages for dialog 1
    dialog1_messages = await message_repo.get_by_dialog(db_conn_clean, test_dialog.id)

    assert len(dialog1_messages) >= 2  # There might be other messages from other tests
    message_texts = {m.text for m in dialog1_messages}
    assert "dialog1_message1" in message_texts
    assert "dialog1_message2" in message_texts
    assert "dialog2_message" not in message_texts

    # Get messages for dialog 2
    dialog2_messages = await message_repo.get_by_dialog(db_conn_clean, created_dialog2.id)

    assert len(dialog2_messages) == 1
    assert dialog2_messages[0].text == "dialog2_message"


async def test_get_thread(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict, test_dialog: Dialog):
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


async def test_message_timestamp_ordering(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict, test_dialog: Dialog):
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

    # Get messages by dialog, should be ordered by timestamp
    dialog_messages = await message_repo.get_by_dialog(db_conn_clean, test_dialog.id)

    # Filter to just our test messages
    test_messages = [m for m in dialog_messages if m.text in ["older_message", "newer_message"]]
    assert len(test_messages) == 2
    assert test_messages[0].text == "older_message"
    assert test_messages[1].text == "newer_message"


async def test_create_message_with_model(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict, test_dialog: Dialog):
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


async def test_message_with_extra_data(db_conn_clean: AsyncConnection, message_repo: MessageRepository, sample_message_data: dict, test_dialog: Dialog):
    # Test with extra data
    extra_data = {"temperature": 0.7, "top_p": 1.0, "tokens": 150}
    message_data = _create_message_data(sample_message_data, extra=extra_data)
    message = Message(**message_data)
    created_message = await message_repo.create(db_conn_clean, message)

    fetched_message = await message_repo.get_by_id(db_conn_clean, created_message.id)
    assert fetched_message.extra == extra_data
