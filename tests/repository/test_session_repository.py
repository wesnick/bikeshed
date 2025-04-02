import pytest
from uuid import uuid4
from datetime import datetime

from psycopg import AsyncConnection
from psycopg.sql import SQL

from core.models import Session, Message, SessionStatus, MessageStatus, WorkflowData
from components.dialog.repository import SessionRepository
from components.message.repository import MessageRepository # Needed to create messages for get_with_messages

pytestmark = pytest.mark.asyncio


@pytest.fixture
def session_repo() -> SessionRepository:
    return SessionRepository()

@pytest.fixture
def message_repo() -> MessageRepository:
    return MessageRepository()


@pytest.fixture
def sample_session_data() -> dict:
    return {
        "description": "Test session description",
        "goal": "Test session goal",
        "status": SessionStatus.PENDING,
        "current_state": "start",
        "workflow_data": WorkflowData(), # Use default WorkflowData
        "template": None, # Assuming template is optional or handled elsewhere
        "error": None,
    }

@pytest.fixture
def sample_message_data(created_session: Session) -> dict:
    """Fixture requires a created_session fixture to link the message"""
    return {
        "session_id": created_session.id,
        "role": "user",
        "text": "Hello, world!",
        "status": MessageStatus.DELIVERED,
    }

@pytest.fixture
async def created_session(db_conn_clean: AsyncConnection, session_repo: SessionRepository, sample_session_data: dict) -> Session:
    """Fixture to create a session and return the persisted object"""
    session = Session(**sample_session_data)
    return await session_repo.create(db_conn_clean, session)


def _create_session_data(base_data: dict, **kwargs) -> dict:
    """Helper to create unique session data for tests."""
    data = base_data.copy()
    # Ensure workflow_data is copied if present and is a model instance
    if 'workflow_data' in data and isinstance(data['workflow_data'], WorkflowData):
        data['workflow_data'] = data['workflow_data'].model_copy()
    data.update(kwargs)
    return data


# === BaseRepository Method Tests ===

async def test_create_session(db_conn_clean: AsyncConnection, session_repo: SessionRepository, sample_session_data: dict):
    session = Session(**sample_session_data)
    created = await session_repo.create(db_conn_clean, session)

    assert created is not None
    assert created.id is not None
    assert created.description == sample_session_data["description"]
    assert created.goal == sample_session_data["goal"]
    assert created.status == SessionStatus.PENDING
    assert created.current_state == "start"
    assert isinstance(created.workflow_data, WorkflowData)
    assert isinstance(created.created_at, datetime)
    assert isinstance(created.updated_at, datetime)


async def test_get_session_by_id(db_conn_clean: AsyncConnection, session_repo: SessionRepository, created_session: Session):
    fetched = await session_repo.get_by_id(db_conn_clean, created_session.id)

    assert fetched is not None
    assert fetched.id == created_session.id
    assert fetched.description == created_session.description


async def test_get_session_by_id_not_found(db_conn_clean: AsyncConnection, session_repo: SessionRepository):
    non_existent_id = uuid4()
    fetched = await session_repo.get_by_id(db_conn_clean, non_existent_id)
    assert fetched is None


async def test_get_all_sessions(db_conn_clean: AsyncConnection, session_repo: SessionRepository, sample_session_data: dict):
    session1_data = _create_session_data(sample_session_data, description="session1")
    session2_data = _create_session_data(sample_session_data, description="session2")
    await session_repo.create(db_conn_clean, Session(**session1_data))
    await session_repo.create(db_conn_clean, Session(**session2_data))

    all_sessions = await session_repo.get_all(db_conn_clean, limit=10)

    assert len(all_sessions) == 2
    descriptions = {s.description for s in all_sessions}
    assert "session1" in descriptions
    assert "session2" in descriptions


async def test_update_session(db_conn_clean: AsyncConnection, session_repo: SessionRepository, created_session: Session):
    update_data = {
        "description": "Updated description",
        "goal": "Updated goal",
        "status": SessionStatus.RUNNING,
        "current_state": "step_1",
        "workflow_data": WorkflowData(current_step_index=1, variables={"key": "value"}),
        "error": "An error occurred"
    }
    updated = await session_repo.update(db_conn_clean, created_session.id, update_data)

    assert updated is not None
    assert updated.id == created_session.id
    assert updated.description == "Updated description"
    assert updated.goal == "Updated goal"
    assert updated.status == SessionStatus.RUNNING
    assert updated.current_state == "step_1"
    assert updated.workflow_data.current_step_index == 1
    assert updated.workflow_data.variables == {"key": "value"}
    assert updated.error == "An error occurred"
    # tests run too fast for this to be true, we verify the db trigger in other places
    # assert updated.updated_at > created_session.updated_at


async def test_update_session_not_found(db_conn_clean: AsyncConnection, session_repo: SessionRepository):
    non_existent_id = uuid4()
    update_data = {"description": "updated_desc"}
    updated = await session_repo.update(db_conn_clean, non_existent_id, update_data)
    assert updated is None


async def test_delete_session(db_conn_clean: AsyncConnection, session_repo: SessionRepository, created_session: Session):
    deleted = await session_repo.delete(db_conn_clean, created_session.id)
    assert deleted is True

    fetched = await session_repo.get_by_id(db_conn_clean, created_session.id)
    assert fetched is None


async def test_delete_session_not_found(db_conn_clean: AsyncConnection, session_repo: SessionRepository):
    non_existent_id = uuid4()
    deleted = await session_repo.delete(db_conn_clean, non_existent_id)
    assert deleted is False


async def test_filter_sessions(db_conn_clean: AsyncConnection, session_repo: SessionRepository, sample_session_data: dict):
    session1_data = _create_session_data(sample_session_data, description="filter_test_1", status=SessionStatus.COMPLETED)
    session2_data = _create_session_data(sample_session_data, description="filter_test_2", status=SessionStatus.RUNNING)
    await session_repo.create(db_conn_clean, Session(**session1_data))
    await session_repo.create(db_conn_clean, Session(**session2_data))

    filtered_sessions = await session_repo.filter(db_conn_clean, {"status": SessionStatus.RUNNING})

    assert len(filtered_sessions) == 1
    assert filtered_sessions[0].description == "filter_test_2"
    assert filtered_sessions[0].status == SessionStatus.RUNNING


async def test_get_session_by_field(db_conn_clean: AsyncConnection, session_repo: SessionRepository, created_session: Session):
    # Test fetching by a unique-ish field like description for this test
    fetched = await session_repo.get_by_field(db_conn_clean, 'description', created_session.description)

    assert fetched is not None
    assert fetched.id == created_session.id
    assert fetched.description == created_session.description


async def test_get_session_by_field_not_found(db_conn_clean: AsyncConnection, session_repo: SessionRepository):
    fetched = await session_repo.get_by_field(db_conn_clean, "description", "non_existent_description")
    assert fetched is None


# === SessionRepository Specific Method Tests ===

async def test_get_recent_sessions(db_conn_clean: AsyncConnection, session_repo: SessionRepository, sample_session_data: dict):
    session1_data = _create_session_data(sample_session_data, description="session_old")
    session1 = Session(**session1_data)
    created1 = await session_repo.create(db_conn_clean, session1)

    # Simulate time passing
    await db_conn_clean.execute(SQL("UPDATE sessions SET created_at = NOW() - INTERVAL '1 second' WHERE id = %s"), (str(created1.id),))

    session2_data = _create_session_data(sample_session_data, description="session_new")
    session2 = Session(**session2_data)
    created2 = await session_repo.create(db_conn_clean, session2)

    recent_sessions = await session_repo.get_recent_sessions(db_conn_clean, limit=1)
    assert len(recent_sessions) == 1
    assert recent_sessions[0].id == created2.id
    assert recent_sessions[0].description == "session_new"

    recent_sessions_all = await session_repo.get_recent_sessions(db_conn_clean, limit=5)
    assert len(recent_sessions_all) == 2
    assert recent_sessions_all[0].id == created2.id # Newest first
    assert recent_sessions_all[1].id == created1.id


async def test_get_active_sessions(db_conn_clean: AsyncConnection, session_repo: SessionRepository, sample_session_data: dict):
    s_running_data = _create_session_data(sample_session_data, description="s_running", status=SessionStatus.RUNNING)
    s_waiting_data = _create_session_data(sample_session_data, description="s_waiting", status=SessionStatus.WAITING_FOR_INPUT)
    s_completed_data = _create_session_data(sample_session_data, description="s_completed", status=SessionStatus.COMPLETED)
    s_failed_data = _create_session_data(sample_session_data, description="s_failed", status=SessionStatus.FAILED)
    s_pending_data = _create_session_data(sample_session_data, description="s_pending", status=SessionStatus.PENDING) # Not active

    await session_repo.create(db_conn_clean, Session(**s_running_data))
    await session_repo.create(db_conn_clean, Session(**s_waiting_data))
    await session_repo.create(db_conn_clean, Session(**s_completed_data))
    await session_repo.create(db_conn_clean, Session(**s_failed_data))
    await session_repo.create(db_conn_clean, Session(**s_pending_data))

    active_sessions = await session_repo.get_active_sessions(db_conn_clean)

    assert len(active_sessions) == 2
    active_descriptions = {s.description for s in active_sessions}
    assert "s_running" in active_descriptions
    assert "s_waiting" in active_descriptions
    assert "s_completed" not in active_descriptions
    assert "s_failed" not in active_descriptions
    assert "s_pending" not in active_descriptions


async def test_get_with_messages(db_conn_clean: AsyncConnection, session_repo: SessionRepository, message_repo: MessageRepository, created_session: Session):
    # Create some messages for the session
    msg1_data = {"session_id": created_session.id, "role": "user", "text": "First message"}
    msg2_data = {"session_id": created_session.id, "role": "assistant", "text": "Second message", "model": "test-model"}

    msg1 = await message_repo.create(db_conn_clean, Message(**msg1_data))
    # Simulate time passing for ordering
    await db_conn_clean.execute(SQL("UPDATE messages SET timestamp = NOW() - INTERVAL '1 second' WHERE id = %s"), (str(msg1.id),))
    msg2 = await message_repo.create(db_conn_clean, Message(**msg2_data))

    # Fetch session with messages
    session_with_messages = await session_repo.get_with_messages(db_conn_clean, created_session.id)

    assert session_with_messages is not None
    assert session_with_messages.id == created_session.id
    assert hasattr(session_with_messages, 'messages')
    assert isinstance(session_with_messages.messages, list)
    assert len(session_with_messages.messages) == 2

    # Check messages are present and ordered correctly by timestamp
    assert session_with_messages.messages[0].id == msg1.id
    assert session_with_messages.messages[0].text == "First message"
    assert session_with_messages.messages[1].id == msg2.id
    assert session_with_messages.messages[1].text == "Second message"


async def test_get_with_messages_no_messages(db_conn_clean: AsyncConnection, session_repo: SessionRepository, created_session: Session):
    # Fetch session that has no messages
    session_with_messages = await session_repo.get_with_messages(db_conn_clean, created_session.id)

    assert session_with_messages is not None
    assert session_with_messages.id == created_session.id
    assert hasattr(session_with_messages, 'messages')
    assert isinstance(session_with_messages.messages, list)
    assert len(session_with_messages.messages) == 0


async def test_get_with_messages_session_not_found(db_conn_clean: AsyncConnection, session_repo: SessionRepository):
    non_existent_id = uuid4()
    session_with_messages = await session_repo.get_with_messages(db_conn_clean, non_existent_id)
    assert session_with_messages is None
