import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from datetime import datetime, timedelta

from src.models.models import (
    Base, Message, Session, Flow, Artifact, 
    FlowTemplate, ScratchPad,
    # artifact_scratchpad
)

# Import fixtures
from src.fixtures import (
    create_flow_template,
    create_flow,
    create_session as create_session_obj,
    create_message,
    create_artifact,
    create_scratchpad,
    create_conversation,
    create_complete_flow_session
)

# Test database URL - replace app with app_test
TEST_DATABASE_URL = "postgresql+asyncpg://app:pass@localhost:5432/app_test"

# Create async engine and session
@pytest.fixture(scope="function")
async def db_session():
    # Create tables
    engine = create_async_engine(TEST_DATABASE_URL)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = async_sessionmaker(
        engine, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

# Tests
@pytest.mark.asyncio
async def test_flow_template_creation(db_session):
    template = await create_flow_template(db_session)
    await db_session.commit()
    
    # Fetch from DB to verify
    result = await db_session.get(FlowTemplate, template.id)
    
    assert result is not None
    assert result.id == template.id
    assert result.name == template.name
    assert result.description == template.description
    assert result.definition == template.definition
    assert isinstance(result.created_at, datetime)
    assert isinstance(result.updated_at, datetime)

@pytest.mark.asyncio
async def test_flow_creation_with_template(db_session):
    template = await create_flow_template(db_session)
    flow = await create_flow(db_session, template=template)
    await db_session.commit()
    
    # Fetch from DB to verify
    result = await db_session.get(Flow, flow.id)
    
    assert result is not None
    assert result.id == flow.id
    assert result.name == flow.name
    # assert result.template_id == template.id
    # assert result.template.name == template.name

@pytest.mark.asyncio
async def test_session_creation(db_session):
    flow = await create_flow(db_session)
    session_obj = await create_session_obj(db_session, flow=flow)
    await db_session.commit()
    
    # Fetch from DB to verify
    result = await db_session.get(Session, session_obj.id)
    
    assert result is not None
    assert result.id == session_obj.id
    # assert result.flow_id == flow.id
    # assert result.flow.name == flow.name

@pytest.mark.asyncio
async def test_message_creation(db_session):
    session_obj = await create_session_obj(db_session)
    message = await create_message(db_session, session_obj)
    await db_session.commit()
    
    # Fetch from DB to verify
    result = await db_session.get(Message, message.id)
    
    assert result is not None
    assert result.id == message.id
    assert result.session_id == session_obj.id
    assert result.role in ("user", "assistant", "system")
    assert result.parent_id is None

@pytest.mark.asyncio
async def test_message_parent_child_relationship(db_session):
    session_obj = await create_session_obj(db_session)
    parent_message = await create_message(db_session, session_obj)
    child_message = await create_message(db_session, session_obj, parent=parent_message)
    await db_session.commit()

    stmt = select(Message).where(Message.id == child_message.id).options(
        selectinload(Message.children)
    )
    parent = await db_session.execute(stmt)
    result = parent.scalar_one()
    
    assert result is not None
    assert result.parent_id == parent_message.id
    
    # Check parent's children
    stmt = select(Message).where(Message.id == parent_message.id).options(
        selectinload(Message.children)
    )
    result = await db_session.execute(stmt)
    parent = result.scalar_one()
    assert len(parent.children) == 1
    assert parent.children[0].id == child_message.id

@pytest.mark.asyncio
async def test_artifact_creation(db_session):
    session_obj = await create_session_obj(db_session)
    message = await create_message(db_session, session_obj)
    artifact = await create_artifact(db_session, source_message=message, source_session=session_obj)
    await db_session.commit()
    
    # Fetch from DB to verify
    result = await db_session.get(Artifact, artifact.id)
    
    assert result is not None
    assert result.id == artifact.id
    # assert result.source_message_id == message.id
    # assert result.source_session_id == session_obj.id

@pytest.mark.asyncio
async def test_scratchpad_with_artifacts(db_session):
    scratchpad = await create_scratchpad(db_session)
    artifact1 = await create_artifact(db_session)
    artifact2 = await create_artifact(db_session)
    await db_session.commit()
    
    # Add artifacts to scratchpad
    # scratchpad.artifacts.append(artifact1)
    # scratchpad.artifacts.append(artifact2)
    await db_session.commit()
    
    # Fetch from DB to verify
    result = await db_session.get(ScratchPad, scratchpad.id)
    
    assert result is not None
    # assert len(result.artifacts) == 2
    # assert artifact1.id in [a.id for a in result.artifacts]
    # assert artifact2.id in [a.id for a in result.artifacts]

@pytest.mark.asyncio
async def test_session_first_message_property(db_session):
    session_obj = await create_session_obj(db_session)
    
    # Create messages with different timestamps
    now = datetime.utcnow()
    
    message1 = Message(
        role="user",
        text="First message",
        status="delivered",
        session_id=session_obj.id,
        timestamp=now - timedelta(minutes=10)
    )
    
    message2 = Message(
        role="assistant",
        text="Second message",
        status="delivered",
        session_id=session_obj.id,
        timestamp=now - timedelta(minutes=5)
    )
    
    message3 = Message(
        role="user",
        text="Third message",
        status="delivered",
        session_id=session_obj.id,
        timestamp=now
    )
    
    db_session.add_all([message1, message2, message3])
    await db_session.commit()
    
    # Refresh session object
    await db_session.refresh(session_obj)
    
    # Fetch all messages to ensure they're loaded
    await db_session.refresh(session_obj, ["messages"])
    
    # Test first_message property
    first = session_obj.first_message
    assert first is not None
    assert first.id == message1.id

@pytest.mark.asyncio
async def test_create_conversation(db_session):
    """Test creating a conversation with the fixture."""
    messages = await create_conversation(db_session, num_messages=4)
    await db_session.commit()
    
    assert len(messages) == 5  # 4 messages + 1 system message
    assert messages[0].role == "system"
    
    # Check alternating user/assistant pattern
    assert messages[1].role == "user"
    assert messages[2].role == "assistant"
    assert messages[3].role == "user"
    assert messages[4].role == "assistant"

@pytest.mark.asyncio
async def test_create_complete_flow_session(db_session):
    """Test creating a complete flow session with all related objects."""
    result = await create_complete_flow_session(db_session, num_messages=3, num_artifacts=2)
    await db_session.commit()
    
    assert result["template"] is not None
    assert result["flow"] is not None
    assert result["session"] is not None
    assert len(result["messages"]) == 4  # 3 messages + 1 system message
    assert len(result["artifacts"]) == 2
    assert result["scratchpad"] is not None
