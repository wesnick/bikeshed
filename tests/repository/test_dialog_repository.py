import pytest
from uuid import uuid4
from datetime import datetime

from psycopg import AsyncConnection
from psycopg.sql import SQL

from src.core.models import Dialog, Message, DialogStatus, MessageStatus, WorkflowData
from src.components.dialog.repository import DialogRepository
from src.components.message.repository import MessageRepository # Needed to create messages for get_with_messages

pytestmark = pytest.mark.asyncio


@pytest.fixture
def dialog_repo() -> DialogRepository:
    return DialogRepository()

@pytest.fixture
def message_repo() -> MessageRepository:
    return MessageRepository()


@pytest.fixture
def sample_dialog_data() -> dict:
    return {
        "description": "Test dialog description",
        "goal": "Test dialog goal",
        "status": DialogStatus.PENDING,
        "current_state": "start",
        "workflow_data": WorkflowData(), # Use default WorkflowData
        "template": None, # Assuming template is optional or handled elsewhere
        "error": None,
    }

@pytest.fixture
def sample_message_data(created_dialog: Dialog) -> dict:
    """Fixture requires a created_dialog fixture to link the message"""
    return {
        "dialog_id": created_dialog.id,
        "role": "user",
        "text": "Hello, world!",
        "status": MessageStatus.DELIVERED,
    }

@pytest.fixture
async def created_dialog(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository, sample_dialog_data: dict) -> Dialog:
    """Fixture to create a dialog and return the persisted object"""
    dialog = Dialog(**sample_dialog_data)
    return await dialog_repo.create(db_conn_clean, dialog)


def _create_dialog_data(base_data: dict, **kwargs) -> dict:
    """Helper to create unique dialog data for tests."""
    data = base_data.copy()
    # Ensure workflow_data is copied if present and is a model instance
    if 'workflow_data' in data and isinstance(data['workflow_data'], WorkflowData):
        data['workflow_data'] = data['workflow_data'].model_copy()
    data.update(kwargs)
    return data


# === BaseRepository Method Tests ===

async def test_create_dialog(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository, sample_dialog_data: dict):
    dialog = Dialog(**sample_dialog_data)
    created = await dialog_repo.create(db_conn_clean, dialog)

    assert created is not None
    assert created.id is not None
    assert created.description == sample_dialog_data["description"]
    assert created.goal == sample_dialog_data["goal"]
    assert created.status == DialogStatus.PENDING
    assert created.current_state == "start"
    assert isinstance(created.workflow_data, WorkflowData)
    assert isinstance(created.created_at, datetime)
    assert isinstance(created.updated_at, datetime)


async def test_get_dialog_by_id(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository, created_dialog: Dialog):
    fetched = await dialog_repo.get_by_id(db_conn_clean, created_dialog.id)

    assert fetched is not None
    assert fetched.id == created_dialog.id
    assert fetched.description == created_dialog.description


async def test_get_dialog_by_id_not_found(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository):
    non_existent_id = uuid4()
    fetched = await dialog_repo.get_by_id(db_conn_clean, non_existent_id)
    assert fetched is None


async def test_get_all_dialogs(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository, sample_dialog_data: dict):
    dialog1_data = _create_dialog_data(sample_dialog_data, description="dialog1")
    dialog2_data = _create_dialog_data(sample_dialog_data, description="dialog2")
    await dialog_repo.create(db_conn_clean, Dialog(**dialog1_data))
    await dialog_repo.create(db_conn_clean, Dialog(**dialog2_data))

    all_dialogs = await dialog_repo.get_all(db_conn_clean, limit=10)

    assert len(all_dialogs) == 2
    descriptions = {s.description for s in all_dialogs}
    assert "dialog1" in descriptions
    assert "dialog2" in descriptions


async def test_update_dialog(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository, created_dialog: Dialog):
    update_data = {
        "description": "Updated description",
        "goal": "Updated goal",
        "status": DialogStatus.RUNNING,
        "current_state": "step_1",
        "workflow_data": WorkflowData(current_step_index=1, variables={"key": "value"}),
        "error": "An error occurred"
    }
    updated = await dialog_repo.update(db_conn_clean, created_dialog.id, update_data)

    assert updated is not None
    assert updated.id == created_dialog.id
    assert updated.description == "Updated description"
    assert updated.goal == "Updated goal"
    assert updated.status == DialogStatus.RUNNING
    assert updated.current_state == "step_1"
    assert updated.workflow_data.current_step_index == 1
    assert updated.workflow_data.variables == {"key": "value"}
    assert updated.error == "An error occurred"
    # tests run too fast for this to be true, we verify the db trigger in other places
    # assert updated.updated_at > created_dialog.updated_at


async def test_update_dialog_not_found(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository):
    non_existent_id = uuid4()
    update_data = {"description": "updated_desc"}
    updated = await dialog_repo.update(db_conn_clean, non_existent_id, update_data)
    assert updated is None


async def test_delete_dialog(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository, created_dialog: Dialog):
    deleted = await dialog_repo.delete(db_conn_clean, created_dialog.id)
    assert deleted is True

    fetched = await dialog_repo.get_by_id(db_conn_clean, created_dialog.id)
    assert fetched is None


async def test_delete_dialog_not_found(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository):
    non_existent_id = uuid4()
    deleted = await dialog_repo.delete(db_conn_clean, non_existent_id)
    assert deleted is False


async def test_filter_dialogs(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository, sample_dialog_data: dict):
    dialog1_data = _create_dialog_data(sample_dialog_data, description="filter_test_1", status=DialogStatus.COMPLETED)
    dialog2_data = _create_dialog_data(sample_dialog_data, description="filter_test_2", status=DialogStatus.RUNNING)
    await dialog_repo.create(db_conn_clean, Dialog(**dialog1_data))
    await dialog_repo.create(db_conn_clean, Dialog(**dialog2_data))

    filtered_dialogs = await dialog_repo.filter(db_conn_clean, {"status": DialogStatus.RUNNING})

    assert len(filtered_dialogs) == 1
    assert filtered_dialogs[0].description == "filter_test_2"
    assert filtered_dialogs[0].status == DialogStatus.RUNNING


async def test_get_dialog_by_field(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository, created_dialog: Dialog):
    # Test fetching by a unique-ish field like description for this test
    fetched = await dialog_repo.get_by_field(db_conn_clean, 'description', created_dialog.description)

    assert fetched is not None
    assert fetched.id == created_dialog.id
    assert fetched.description == created_dialog.description


async def test_get_dialog_by_field_not_found(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository):
    fetched = await dialog_repo.get_by_field(db_conn_clean, "description", "non_existent_description")
    assert fetched is None


# === DialogRepository Specific Method Tests ===

async def test_get_recent_dialogs(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository, sample_dialog_data: dict):
    dialog1_data = _create_dialog_data(sample_dialog_data, description="dialog_old")
    dialog1 = Dialog(**dialog1_data)
    created1 = await dialog_repo.create(db_conn_clean, dialog1)

    # Simulate time passing
    await db_conn_clean.execute(SQL("UPDATE dialogs SET created_at = NOW() - INTERVAL '1 second' WHERE id = %s"), (str(created1.id),))

    dialog2_data = _create_dialog_data(sample_dialog_data, description="dialog_new")
    dialog2 = Dialog(**dialog2_data)
    created2 = await dialog_repo.create(db_conn_clean, dialog2)

    recent_dialogs = await dialog_repo.get_recent_dialogs(db_conn_clean, limit=1)
    assert len(recent_dialogs) == 1
    assert recent_dialogs[0].id == created2.id
    assert recent_dialogs[0].description == "dialog_new"

    recent_dialogs_all = await dialog_repo.get_recent_dialogs(db_conn_clean, limit=5)
    assert len(recent_dialogs_all) == 2
    assert recent_dialogs_all[0].id == created2.id # Newest first
    assert recent_dialogs_all[1].id == created1.id


async def test_get_active_dialogs(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository, sample_dialog_data: dict):
    s_running_data = _create_dialog_data(sample_dialog_data, description="s_running", status=DialogStatus.RUNNING)
    s_waiting_data = _create_dialog_data(sample_dialog_data, description="s_waiting", status=DialogStatus.WAITING_FOR_INPUT)
    s_completed_data = _create_dialog_data(sample_dialog_data, description="s_completed", status=DialogStatus.COMPLETED)
    s_failed_data = _create_dialog_data(sample_dialog_data, description="s_failed", status=DialogStatus.FAILED)
    s_pending_data = _create_dialog_data(sample_dialog_data, description="s_pending", status=DialogStatus.PENDING) # Not active

    await dialog_repo.create(db_conn_clean, Dialog(**s_running_data))
    await dialog_repo.create(db_conn_clean, Dialog(**s_waiting_data))
    await dialog_repo.create(db_conn_clean, Dialog(**s_completed_data))
    await dialog_repo.create(db_conn_clean, Dialog(**s_failed_data))
    await dialog_repo.create(db_conn_clean, Dialog(**s_pending_data))

    active_dialogs = await dialog_repo.get_active_dialogs(db_conn_clean)

    assert len(active_dialogs) == 2
    active_descriptions = {s.description for s in active_dialogs}
    assert "s_running" in active_descriptions
    assert "s_waiting" in active_descriptions
    assert "s_completed" not in active_descriptions
    assert "s_failed" not in active_descriptions
    assert "s_pending" not in active_descriptions


async def test_get_with_messages(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository, message_repo: MessageRepository, created_dialog: Dialog):
    # Create some messages for the dialog
    msg1_data = {"dialog_id": created_dialog.id, "role": "user", "text": "First message"}
    msg2_data = {"dialog_id": created_dialog.id, "role": "assistant", "text": "Second message", "model": "test-model"}

    msg1 = await message_repo.create(db_conn_clean, Message(**msg1_data))
    # Simulate time passing for ordering
    await db_conn_clean.execute(SQL("UPDATE messages SET timestamp = NOW() - INTERVAL '1 second' WHERE id = %s"), (str(msg1.id),))
    msg2 = await message_repo.create(db_conn_clean, Message(**msg2_data))

    # Fetch dialog with messages
    dialog_with_messages = await dialog_repo.get_with_messages(db_conn_clean, created_dialog.id)

    assert dialog_with_messages is not None
    assert dialog_with_messages.id == created_dialog.id
    assert hasattr(dialog_with_messages, 'messages')
    assert isinstance(dialog_with_messages.messages, list)
    assert len(dialog_with_messages.messages) == 2

    # Check messages are present and ordered correctly by timestamp
    assert dialog_with_messages.messages[0].id == msg1.id
    assert dialog_with_messages.messages[0].text == "First message"
    assert dialog_with_messages.messages[1].id == msg2.id
    assert dialog_with_messages.messages[1].text == "Second message"


async def test_get_with_messages_no_messages(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository, created_dialog: Dialog):
    # Fetch dialog that has no messages
    dialog_with_messages = await dialog_repo.get_with_messages(db_conn_clean, created_dialog.id)

    assert dialog_with_messages is not None
    assert dialog_with_messages.id == created_dialog.id
    assert hasattr(dialog_with_messages, 'messages')
    assert isinstance(dialog_with_messages.messages, list)
    assert len(dialog_with_messages.messages) == 0


async def test_get_with_messages_dialog_not_found(db_conn_clean: AsyncConnection, dialog_repo: DialogRepository):
    non_existent_id = uuid4()
    dialog_with_messages = await dialog_repo.get_with_messages(db_conn_clean, non_existent_id)
    assert dialog_with_messages is None
