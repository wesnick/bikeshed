import uuid
import pytest
from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from datetime import datetime, timedelta

from src.models.models import (
    Base, Message, Session, Flow, Artifact, 
    FlowTemplate, ScratchPad, artifact_scratchpad
)

# Initialize Faker
fake = Faker()

# Test database URL - replace app with app_test
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/app_test"

# Create async engine and session
@pytest.fixture(scope="function")
async def db_session():
    # Create tables
    engine = create_async_engine(TEST_DATABASE_URL)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

# Helper functions to create test data
async def create_flow_template(session):
    template = FlowTemplate(
        name=fake.word(),
        description=fake.paragraph(),
        definition={"steps": [{"name": "step1", "action": "test"}]}
    )
    session.add(template)
    await session.commit()
    return template

async def create_flow(session, template=None):
    flow = Flow(
        name=fake.word(),
        description=fake.paragraph(),
        goal=fake.sentence(),
        strategy="sequential",
        current_state="initial",
        workflow_definition={"steps": [{"name": "step1", "action": "test"}]},
        template_id=template.id if template else None
    )
    session.add(flow)
    await session.commit()
    return flow

async def create_session_obj(session, flow=None, template=None):
    session_obj = Session(
        summary=fake.paragraph(),
        goal=fake.sentence(),
        system_prompt=fake.paragraph(),
        strategy="task_decomposition",
        flow_id=flow.id if flow else None,
        template_id=template.id if template else None
    )
    session.add(session_obj)
    await session.commit()
    return session_obj

async def create_message(session, session_obj, parent=None):
    message = Message(
        role=fake.random_element(elements=("user", "assistant", "system")),
        model="gpt-4",
        text=fake.paragraph(),
        status="delivered",
        mime_type="text/plain",
        session_id=session_obj.id,
        parent_id=parent.id if parent else None,
        extra={"temperature": 0.7}
    )
    session.add(message)
    await session.commit()
    return message

async def create_artifact(session, message=None, session_obj=None, flow=None):
    artifact = Artifact(
        name=fake.file_name(),
        description=fake.sentence(),
        mime_type=fake.mime_type(),
        content_text=fake.paragraph() if fake.boolean() else None,
        content_path=f"/path/to/{fake.file_name()}" if fake.boolean() else None,
        source_message_id=message.id if message else None,
        source_session_id=session_obj.id if session_obj else None,
        source_flow_id=flow.id if flow else None,
        extra={"size": fake.random_int(min=1000, max=10000)}
    )
    session.add(artifact)
    await session.commit()
    return artifact

async def create_scratchpad(session):
    scratchpad = ScratchPad(
        name=fake.word(),
        description=fake.paragraph(),
        notes=fake.paragraph()
    )
    session.add(scratchpad)
    await session.commit()
    return scratchpad

# Tests
@pytest.mark.asyncio
async def test_flow_template_creation(db_session):
    template = await create_flow_template(db_session)
    
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
    flow = await create_flow(db_session, template)
    
    # Fetch from DB to verify
    result = await db_session.get(Flow, flow.id)
    
    assert result is not None
    assert result.id == flow.id
    assert result.name == flow.name
    assert result.template_id == template.id
    assert result.template.name == template.name

@pytest.mark.asyncio
async def test_session_creation(db_session):
    flow = await create_flow(db_session)
    session_obj = await create_session_obj(db_session, flow)
    
    # Fetch from DB to verify
    result = await db_session.get(Session, session_obj.id)
    
    assert result is not None
    assert result.id == session_obj.id
    assert result.flow_id == flow.id
    assert result.flow.name == flow.name

@pytest.mark.asyncio
async def test_message_creation(db_session):
    session_obj = await create_session_obj(db_session)
    message = await create_message(db_session, session_obj)
    
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
    child_message = await create_message(db_session, session_obj, parent_message)
    
    # Fetch from DB to verify
    result = await db_session.get(Message, child_message.id)
    
    assert result is not None
    assert result.parent_id == parent_message.id
    
    # Check parent's children
    parent = await db_session.get(Message, parent_message.id)
    assert len(parent.children) == 1
    assert parent.children[0].id == child_message.id

@pytest.mark.asyncio
async def test_artifact_creation(db_session):
    session_obj = await create_session_obj(db_session)
    message = await create_message(db_session, session_obj)
    artifact = await create_artifact(db_session, message, session_obj)
    
    # Fetch from DB to verify
    result = await db_session.get(Artifact, artifact.id)
    
    assert result is not None
    assert result.id == artifact.id
    assert result.source_message_id == message.id
    assert result.source_session_id == session_obj.id

@pytest.mark.asyncio
async def test_scratchpad_with_artifacts(db_session):
    scratchpad = await create_scratchpad(db_session)
    artifact1 = await create_artifact(db_session)
    artifact2 = await create_artifact(db_session)
    
    # Add artifacts to scratchpad
    scratchpad.artifacts.append(artifact1)
    scratchpad.artifacts.append(artifact2)
    await db_session.commit()
    
    # Fetch from DB to verify
    result = await db_session.get(ScratchPad, scratchpad.id)
    
    assert result is not None
    assert len(result.artifacts) == 2
    assert artifact1.id in [a.id for a in result.artifacts]
    assert artifact2.id in [a.id for a in result.artifacts]

@pytest.mark.asyncio
async def test_session_first_message_property(db_session):
    session_obj = await create_session_obj(db_session)
    
    # Create messages with different timestamps
    now = datetime.utcnow()
    
    message1 = Message(
        role="user",
        text=fake.paragraph(),
        status="delivered",
        session_id=session_obj.id,
        timestamp=now - timedelta(minutes=10)
    )
    
    message2 = Message(
        role="assistant",
        text=fake.paragraph(),
        status="delivered",
        session_id=session_obj.id,
        timestamp=now - timedelta(minutes=5)
    )
    
    message3 = Message(
        role="user",
        text=fake.paragraph(),
        status="delivered",
        session_id=session_obj.id,
        timestamp=now
    )
    
    db_session.add_all([message1, message2, message3])
    await db_session.commit()
    
    # Refresh session object
    await db_session.refresh(session_obj)
    
    # Test first_message property
    first = session_obj.first_message
    assert first is not None
    assert first.id == message1.id
