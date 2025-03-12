import uuid
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable

from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.models import (
    Message, Session, Flow, Artifact, FlowTemplate, ScratchPad
)

fake = Faker()

async def create_flow_template(
    session: AsyncSession,
    name: Optional[str] = None,
    description: Optional[str] = None,
    definition: Optional[Dict] = None
) -> FlowTemplate:
    """Create a flow template with sensible defaults."""
    template = FlowTemplate(
        id=uuid.uuid4(),
        name=name or fake.bs(),
        description=description or fake.paragraph(),
        definition=definition or {
            "steps": [
                {"name": "step1", "description": fake.sentence()},
                {"name": "step2", "description": fake.sentence()},
                {"name": "step3", "description": fake.sentence()}
            ],
            "transitions": [
                {"from": "step1", "to": "step2", "condition": "success"},
                {"from": "step2", "to": "step3", "condition": "success"}
            ]
        },
        created_at=fake.date_time_this_year(),
        updated_at=fake.date_time_this_month()
    )
    
    session.add(template)
    await session.flush()
    return template

async def create_flow(
    session: AsyncSession,
    template: Optional[FlowTemplate] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    goal: Optional[str] = None,
    strategy: Optional[str] = None,
    current_state: Optional[str] = None,
    workflow_definition: Optional[Dict] = None
) -> Flow:
    """Create a flow with sensible defaults."""
    if template:
        template_id = template.id
        workflow_definition = workflow_definition or template.definition
    else:
        template_id = None
        workflow_definition = workflow_definition or {
            "steps": [
                {"name": "step1", "description": fake.sentence()},
                {"name": "step2", "description": fake.sentence()}
            ],
            "transitions": [
                {"from": "step1", "to": "step2", "condition": "success"}
            ]
        }
    
    flow = Flow(
        id=uuid.uuid4(),
        name=name or fake.catch_phrase(),
        description=description or fake.paragraph(),
        goal=goal or fake.sentence(),
        strategy=strategy or random.choice(["sequential", "parallel", "adaptive"]),
        current_state=current_state or "step1",
        workflow_definition=workflow_definition,
        created_at=fake.date_time_this_year(),
        updated_at=fake.date_time_this_month(),
        template_id=template_id
    )
    
    session.add(flow)
    await session.flush()
    return flow

async def create_session(
    session: AsyncSession,
    flow: Optional[Flow] = None,
    template: Optional[FlowTemplate] = None,
    summary: Optional[str] = None,
    goal: Optional[str] = None,
    system_prompt: Optional[str] = None,
    strategy: Optional[str] = None
) -> Session:
    """Create a session with sensible defaults."""
    session_obj = Session(
        id=uuid.uuid4(),
        flow_id=flow.id if flow else None,
        summary=summary or fake.paragraph(),
        goal=goal or fake.sentence(),
        system_prompt=system_prompt or "You are a helpful assistant.",
        strategy=strategy or random.choice(["task_decomposition", "chain_of_thought", "direct"]),
        created_at=fake.date_time_this_year(),
        template_id=template.id if template else None
    )
    
    session.add(session_obj)
    await session.flush()
    return session_obj

async def create_message(
    session: AsyncSession,
    session_obj: Session,
    parent: Optional[Message] = None,
    role: Optional[str] = None,
    model: Optional[str] = None,
    text: Optional[str] = None,
    status: Optional[str] = None,
    mime_type: Optional[str] = None,
    extra: Optional[Dict] = None
) -> Message:
    """Create a message with sensible defaults."""
    roles = ["user", "assistant", "system"]
    models = ["gpt-4", "gpt-3.5-turbo", "claude-3-opus", "claude-3-sonnet"]
    statuses = ["created", "pending", "delivered", "failed"]
    
    message = Message(
        id=uuid.uuid4(),
        parent_id=parent.id if parent else None,
        session_id=session_obj.id,
        role=role or random.choice(roles),
        model=model or random.choice(models),
        text=text or fake.paragraph(),
        status=status or random.choice(statuses),
        mime_type=mime_type or "text/plain",
        timestamp=fake.date_time_this_month(),
        extra=extra or {"temperature": 0.7, "max_tokens": 1000}
    )
    
    session.add(message)
    await session.flush()
    return message

async def create_artifact(
    session: AsyncSession,
    name: Optional[str] = None,
    description: Optional[str] = None,
    mime_type: Optional[str] = None,
    content_path: Optional[str] = None,
    content_text: Optional[str] = None,
    source_message: Optional[Message] = None,
    source_session: Optional[Session] = None,
    source_flow: Optional[Flow] = None,
    extra: Optional[Dict] = None
) -> Artifact:
    """Create an artifact with sensible defaults."""
    mime_types = ["text/plain", "text/markdown", "application/json", "image/png", "application/pdf"]
    
    artifact = Artifact(
        id=uuid.uuid4(),
        name=name or fake.file_name(),
        description=description or fake.sentence(),
        mime_type=mime_type or random.choice(mime_types),
        content_path=content_path or (f"/path/to/files/{fake.file_name()}" if random.choice([True, False]) else None),
        content_text=content_text or (fake.text() if not content_path else None),
        source_message_id=source_message.id if source_message else None,
        source_session_id=source_session.id if source_session else None,
        source_flow_id=source_flow.id if source_flow else None,
        created_at=fake.date_time_this_year(),
        updated_at=fake.date_time_this_month(),
        extra=extra or {"size": random.randint(1000, 10000000), "version": "1.0"}
    )
    
    session.add(artifact)
    await session.flush()
    return artifact

async def create_scratchpad(
    session: AsyncSession,
    name: Optional[str] = None,
    description: Optional[str] = None,
    notes: Optional[Dict] = None
) -> ScratchPad:
    """Create a scratchpad with sensible defaults."""
    scratchpad = ScratchPad(
        id=uuid.uuid4(),
        name=name or f"Scratchpad {fake.word()}",
        description=description or fake.paragraph(),
        notes=notes or {"ideas": [fake.sentence() for _ in range(3)], "references": [fake.url() for _ in range(2)]},
        created_at=fake.date_time_this_year(),
        updated_at=fake.date_time_this_month()
    )
    
    session.add(scratchpad)
    await session.flush()
    return scratchpad

async def create_conversation(
    session: AsyncSession, 
    num_messages: int = 5,
    session_obj: Optional[Session] = None
) -> List[Message]:
    """Create a conversation with alternating user and assistant messages."""
    if not session_obj:
        session_obj = await create_session(session)
    
    messages = []
    parent = None
    
    # Create system message first
    system_message = await create_message(
        session=session,
        session_obj=session_obj,
        role="system",
        text=session_obj.system_prompt or "You are a helpful assistant.",
        status="delivered"
    )
    messages.append(system_message)
    
    # Create alternating user and assistant messages
    for i in range(num_messages):
        role = "user" if i % 2 == 0 else "assistant"
        
        if role == "user":
            text = fake.paragraph()
            model = None
        else:
            text = fake.paragraph(nb_sentences=random.randint(3, 8))
            model = random.choice(["gpt-4", "gpt-3.5-turbo", "claude-3-opus"])
        
        message = await create_message(
            session=session,
            session_obj=session_obj,
            parent=parent,
            role=role,
            model=model,
            text=text,
            status="delivered"
        )
        
        messages.append(message)
        parent = message
    
    return messages

async def create_complete_flow_session(
    session: AsyncSession,
    num_messages: int = 5,
    num_artifacts: int = 2
) -> Dict[str, Any]:
    """Create a complete flow with template, session, messages and artifacts."""
    # Create template
    template = await create_flow_template(session)
    
    # Create flow based on template
    flow = await create_flow(session, template=template)
    
    # Create session based on flow
    session_obj = await create_session(session, flow=flow, template=template)
    
    # Create conversation
    messages = await create_conversation(session, num_messages, session_obj)
    
    # Create artifacts
    artifacts = []
    for _ in range(num_artifacts):
        # Randomly choose a source for the artifact
        source_type = random.choice(["message", "session", "flow"])
        
        if source_type == "message":
            artifact = await create_artifact(
                session=session,
                source_message=random.choice(messages)
            )
        elif source_type == "session":
            artifact = await create_artifact(
                session=session,
                source_session=session_obj
            )
        else:
            artifact = await create_artifact(
                session=session,
                source_flow=flow
            )
        
        artifacts.append(artifact)
    
    # Create scratchpad
    scratchpad = await create_scratchpad(session)
    
    return {
        "template": template,
        "flow": flow,
        "session": session_obj,
        "messages": messages,
        "artifacts": artifacts,
        "scratchpad": scratchpad
    }
