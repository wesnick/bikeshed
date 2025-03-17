from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime

# Import the database models (these would be in your models.py file)
from .models import Message, Session as DBSession, Flow, Artifact, FlowTemplate, ScratchPad
from .database import get_db
from .workflow_engine import WorkflowEngine


# Pydantic models for request/response
class MessageBase(BaseModel):
    role: str
    model: Optional[str] = None
    text: str
    mime_type: str = "text/plain"
    extra: Optional[Dict[str, Any]] = None


class MessageCreate(MessageBase):
    session_id: UUID
    parent_id: Optional[UUID] = None


class MessageResponse(MessageBase):
    id: UUID
    parent_id: Optional[UUID] = None
    session_id: UUID
    status: str
    timestamp: datetime

    class Config:
        orm_mode = True


class SessionBase(BaseModel):
    summary: Optional[str] = None
    goal: Optional[str] = None
    system_prompt: Optional[str] = None
    strategy: Optional[str] = None


class SessionCreate(SessionBase):
    flow_id: Optional[UUID] = None
    template_id: Optional[UUID] = None


class SessionResponse(SessionBase):
    id: UUID
    flow_id: Optional[UUID] = None
    created_at: datetime
    template_id: Optional[UUID] = None

    class Config:
        orm_mode = True


class FlowBase(BaseModel):
    name: str
    description: Optional[str] = None
    goal: Optional[str] = None
    strategy: Optional[str] = None
    workflow_definition: Optional[Dict[str, Any]] = None


class FlowCreate(FlowBase):
    template_id: Optional[UUID] = None


class FlowResponse(FlowBase):
    id: UUID
    current_state: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    template_id: Optional[UUID] = None

    class Config:
        orm_mode = True


class ArtifactBase(BaseModel):
    name: str
    description: Optional[str] = None
    mime_type: str


class ArtifactCreate(ArtifactBase):
    source_message_id: Optional[UUID] = None
    source_session_id: Optional[UUID] = None
    source_flow_id: Optional[UUID] = None
    content_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ArtifactResponse(ArtifactBase):
    id: UUID
    content_path: Optional[str] = None
    content_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        orm_mode = True


class FlowTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    definition: Dict[str, Any]


class FlowTemplateCreate(FlowTemplateBase):
    pass


class FlowTemplateResponse(FlowTemplateBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ScratchPadBase(BaseModel):
    name: str
    description: Optional[str] = None
    notes: Optional[str] = None


class ScratchPadCreate(ScratchPadBase):
    pass


class ScratchPadResponse(ScratchPadBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


# Router instances
message_router = APIRouter(prefix="/api/messages", tags=["messages"])
session_router = APIRouter(prefix="/api/sessions", tags=["sessions"])
flow_router = APIRouter(prefix="/api/flows", tags=["flows"])
artifact_router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])
template_router = APIRouter(prefix="/api/templates", tags=["templates"])
scratchpad_router = APIRouter(prefix="/api/scratchpads", tags=["scratchpads"])


# Message routes
@message_router.post("/", response_model=MessageResponse)
def create_message(message: MessageCreate, db: Session = Depends(get_db)):
    db_message = Message(
        role=message.role,
        model=message.model,
        text=message.text,
        mime_type=message.mime_type,
        session_id=message.session_id,
        parent_id=message.parent_id,
        extra=message.extra
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


@message_router.get("/{message_id}", response_model=MessageResponse)
def get_message(message_id: UUID, db: Session = Depends(get_db)):
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message


@message_router.get("/session/{session_id}", response_model=List[MessageResponse])
def get_session_messages(session_id: UUID, db: Session = Depends(get_db)):
    messages = db.query(Message).filter(Message.session_id == session_id).all()
    return messages


# Session routes
@session_router.post("/", response_model=SessionResponse)
def create_session(session: SessionCreate, db: Session = Depends(get_db)):
    db_session = DBSession(
        flow_id=session.flow_id,
        summary=session.summary,
        goal=session.goal,
        system_prompt=session.system_prompt,
        strategy=session.strategy,
        template_id=session.template_id
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session


@session_router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: UUID, db: Session = Depends(get_db)):
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@session_router.get("/flow/{flow_id}", response_model=List[SessionResponse])
def get_flow_sessions(flow_id: UUID, db: Session = Depends(get_db)):
    sessions = db.query(DBSession).filter(DBSession.flow_id == flow_id).all()
    return sessions


# Flow routes
@flow_router.post("/", response_model=FlowResponse)
def create_flow(flow: FlowCreate, db: Session = Depends(get_db)):
    db_flow = Flow(
        name=flow.name,
        description=flow.description,
        goal=flow.goal,
        strategy=flow.strategy,
        workflow_definition=flow.workflow_definition,
        template_id=flow.template_id
    )
    db.add(db_flow)
    db.commit()
    db.refresh(db_flow)
    return db_flow


@flow_router.get("/{flow_id}", response_model=FlowResponse)
def get_flow(flow_id: UUID, db: Session = Depends(get_db)):
    flow = db.query(Flow).filter(Flow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


@flow_router.put("/{flow_id}/state", response_model=FlowResponse)
def update_flow_state(
        flow_id: UUID,
        state_update: Dict[str, Any],
        db: Session = Depends(get_db),
        workflow_engine: WorkflowEngine = Depends()
):
    flow = db.query(Flow).filter(Flow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    # Use workflow engine to update state
    new_state = workflow_engine.transition(
        flow.current_state,
        state_update.get("transition"),
        flow.workflow_definition
    )

    flow.current_state = new_state
    flow.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(flow)
    return flow


# Artifact routes
@artifact_router.post("/", response_model=ArtifactResponse)
def create_artifact(artifact: ArtifactCreate, db: Session = Depends(get_db)):
    db_artifact = Artifact(
        name=artifact.name,
        description=artifact.description,
        mime_type=artifact.mime_type,
        source_message_id=artifact.source_message_id,
        source_session_id=artifact.source_session_id,
        source_flow_id=artifact.source_flow_id,
        content_text=artifact.content_text,
        metadata=artifact.metadata
    )
    db.add(db_artifact)
    db.commit()
    db.refresh(db_artifact)
    return db_artifact


@artifact_router.post("/upload", response_model=ArtifactResponse)
async def upload_artifact(
        name: str,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
        source_message_id: Optional[UUID] = None,
        source_session_id: Optional[UUID] = None,
        source_flow_id: Optional[UUID] = None,
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    # Handle file upload and storage (implementation depends on your storage solution)
    content_path = f"uploads/{file.filename}"

    # Save file content
    with open(content_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    # Detect mime_type if not provided
    if not mime_type:
        mime_type = file.content_type

    # Create artifact record
    db_artifact = Artifact(
        name=name or file.filename,
        description=description,
        mime_type=mime_type,
        source_message_id=source_message_id,
        source_session_id=source_session_id,
        source_flow_id=source_flow_id,
        content_path=content_path,
        metadata={"size": len(content), "filename": file.filename}
    )
    db.add(db_artifact)
    db.commit()
    db.refresh(db_artifact)
    return db_artifact


@artifact_router.get("/{artifact_id}", response_model=ArtifactResponse)
def get_artifact(artifact_id: UUID, db: Session = Depends(get_db)):
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


# Template routes
@template_router.post("/", response_model=FlowTemplateResponse)
def create_template(template: FlowTemplateCreate, db: Session = Depends(get_db)):
    db_template = FlowTemplate(
        name=template.name,
        description=template.description,
        definition=template.definition
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


@template_router.get("/{template_id}", response_model=FlowTemplateResponse)
def get_template(template_id: UUID, db: Session = Depends(get_db)):
    template = db.query(FlowTemplate).filter(FlowTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@template_router.post("/{template_id}/instantiate", response_model=FlowResponse)
def instantiate_flow_from_template(template_id: UUID, db: Session = Depends(get_db)):
    template = db.query(FlowTemplate).filter(FlowTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Create new flow from template
    new_flow = Flow(
        name=f"{template.name} Instance",
        description=template.description,
        workflow_definition=template.definition.get("workflow"),
        template_id=template.id
    )
    db.add(new_flow)
    db.commit()
    db.refresh(new_flow)

    # Create initial sessions based on template
    for session_def in template.definition.get("sessions", []):
        new_session = DBSession(
            flow_id=new_flow.id,
            goal=session_def.get("goal"),
            system_prompt=session_def.get("system_prompt"),
            strategy=session_def.get("strategy"),
            template_id=template.id
        )
        db.add(new_session)

    db.commit()
    return new_flow


# ScratchPad routes
@scratchpad_router.post("/", response_model=ScratchPadResponse)
def create_scratchpad(scratchpad: ScratchPadCreate, db: Session = Depends(get_db)):
    db_scratchpad = ScratchPad(
        name=scratchpad.name,
        description=scratchpad.description,
        notes=scratchpad.notes
    )
    db.add(db_scratchpad)
    db.commit()
    db.refresh(db_scratchpad)
    return db_scratchpad


@scratchpad_router.get("/{scratchpad_id}", response_model=ScratchPadResponse)
def get_scratchpad(scratchpad_id: UUID, db: Session = Depends(get_db)):
    scratchpad = db.query(ScratchPad).filter(ScratchPad.id == scratchpad_id).first()
    if not scratchpad:
        raise HTTPException(status_code=404, detail="ScratchPad not found")
    return scratchpad


@scratchpad_router.post("/{scratchpad_id}/artifacts/{artifact_id}")
def link_artifact_to_scratchpad(
        scratchpad_id: UUID,
        artifact_id: UUID,
        db: Session = Depends(get_db)
):
    scratchpad = db.query(ScratchPad).filter(ScratchPad.id == scratchpad_id).first()
    if not scratchpad:
        raise HTTPException(status_code=404, detail="ScratchPad not found")

    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    scratchpad.artifacts.append(artifact)
    db.commit()
    return {"status": "success"}


@scratchpad_router.delete("/{scratchpad_id}/artifacts/{artifact_id}")
def unlink_artifact_from_scratchpad(
        scratchpad_id: UUID,
        artifact_id: UUID,
        db: Session = Depends(get_db)
):
    scratchpad = db.query(ScratchPad).filter(ScratchPad.id == scratchpad_id).first()
    if not scratchpad:
        raise HTTPException(status_code=404, detail="ScratchPad not found")

    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    if artifact in scratchpad.artifacts:
        scratchpad.artifacts.remove(artifact)
        db.commit()

    return {"status": "success"}




## Models

#
# class Flow(Base):
#     __tablename__ = 'flows'
#
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#
#     name = Column(String(255), nullable=False)
#     description = Column(Text, nullable=True)
#     goal = Column(Text, nullable=True)
#     strategy = Column(String(100), nullable=True)  # workflow, sequence, etc.
#
#     # State machine properties
#     current_state = Column(String(100), nullable=True)
#     workflow_definition = Column(JSONB, nullable=True)  # YAML workflow as JSON
#
#     created_at = Column(DateTime, default=datetime.now)
#     updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
#     template_id = Column(UUID(as_uuid=True), ForeignKey('flow_templates.id'), nullable=True)
#
#     # Relationships
#     # sessions = relationship("Session", back_populates="flow")
#     # artifacts = relationship("Artifact", back_populates="source_flow")
#     # template = relationship("FlowTemplate", back_populates="derived_flows")
#
#
# class Artifact(Base):
#     __tablename__ = 'artifacts'
#
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#
#     name = Column(String(255), nullable=False)
#     description = Column(Text, nullable=True)
#     mime_type = Column(String(100), nullable=False)
#     content_path = Column(String(255), nullable=True)  # Path to stored content if binary
#     content_text = Column(Text, nullable=True)  # Direct content if text
#
#     # Can be linked to any source
#     source_message_id = Column(UUID(as_uuid=True), ForeignKey('messages.id'), nullable=True)
#     source_session_id = Column(UUID(as_uuid=True), ForeignKey('sessions.id'), nullable=True)
#     source_flow_id = Column(UUID(as_uuid=True), ForeignKey('flows.id'), nullable=True)
#
#     created_at = Column(DateTime, default=datetime.now)
#     updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
#     extra = Column(JSONB, nullable=True)  # For file size, dimensions, etc.
#
#     # Relationships
#     # source_message = relationship("Message", back_populates="artifacts")
#     # source_session = relationship("Session", back_populates="artifacts")
#     # source_flow = relationship("Flow", back_populates="artifacts")
#     # scratchpads = relationship("ScratchPad", secondary=artifact_scratchpad, back_populates="scratchpads")
#
#
# class FlowTemplate(Base):
#     __tablename__ = 'flow_templates'
#
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#
#     name = Column(String(255), nullable=False)
#     description = Column(Text, nullable=True)
#     definition = Column(JSONB, nullable=False)  # Template definition as JSON
#
#     created_at = Column(DateTime, default=datetime.now)
#     updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
#
#     # Relationships
#     # derived_flows = relationship("Flow", back_populates="template")
#     # derived_sessions = relationship("Session", back_populates="template")
#
#
# class ScratchPad(Base):
#     __tablename__ = 'scratchpads'
#
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#
#     name = Column(String(255), nullable=False)
#     description = Column(Text, nullable=True)
#     notes = Column(JSONB, nullable=True)  # Additional free-form notes
#
#     created_at = Column(DateTime, default=datetime.now)
#     updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
#
#     # Relationships
#     # artifacts = relationship("Artifact", secondary=artifact_scratchpad, back_populates="scratchpads")
