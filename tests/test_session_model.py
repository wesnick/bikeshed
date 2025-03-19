import pytest
import uuid
from datetime import datetime

from src.models.models import Session, Message
from src.core.config_types import SessionTemplate, Step, MessageStep


@pytest.fixture
def session_template():
    """Create a sample session template with steps"""
    return SessionTemplate(
        name="Test Template",
        description="A template for testing",
        model="test-model",
        steps=[
            MessageStep(
                name="step1",
                type="message",
                role="system",
                content="Step 1 content",
                enabled=True
            ),
            MessageStep(
                name="step2",
                type="message",
                role="system",
                content="Step 2 content",
                enabled=True
            ),
            MessageStep(
                name="disabled_step",
                type="message",
                role="system",
                content="Disabled step content",
                enabled=False
            ),
        ]
    )


@pytest.fixture
def session(session_template):
    """Create a sample session with workflow data"""
    return Session(
        id=uuid.uuid4(),
        description="Test Session",
        template=session_template,
        created_at=datetime.now(),
        status="running",
        current_state="step1",
        workflow_data={
            "current_step_index": 1,
            "step_results": {
                "step1": {
                    "completed": True,
                    "message_id": str(uuid.uuid4())
                }
            },
            "variables": {
                "test_var": "test_value"
            },
            "errors": []
        }
    )


@pytest.fixture
def session_with_messages(session):
    """Create a session with messages"""
    message1 = Message(
        id=uuid.uuid4(),
        session_id=session.id,
        role="system",
        text="First message",
        timestamp=datetime(2023, 1, 1, 10, 0, 0)
    )
    
    message2 = Message(
        id=uuid.uuid4(),
        session_id=session.id,
        role="user",
        text="Second message",
        timestamp=datetime(2023, 1, 1, 10, 1, 0)
    )
    
    session.messages = [message1, message2]
    return session


class TestSessionModel:
    
    def test_get_current_step(self, session):
        """Test getting the current step from the template"""
        current_step = session.get_current_step()
        assert current_step is not None
        assert current_step.name == "step2"
        assert current_step.content == "Step 2 content"
        
        # Test with an index beyond the steps
        session.workflow_data["current_step_index"] = 5
        assert session.get_current_step() is None
        
        # Test with no template
        session.template = None
        assert session.get_current_step() is None
    
    def test_is_complete(self, session):
        """Test checking if the workflow is complete"""
        # Not complete yet
        assert session.is_complete() is False
        
        # Set to complete
        session.workflow_data["current_step_index"] = 2
        assert session.is_complete() is True
        
        # Test with no template
        session.template = None
        assert session.is_complete() is False
    
    def test_get_step_result(self, session):
        """Test getting a step result"""
        # Get existing step result
        result = session.get_step_result("step1")
        assert result is not None
        assert result["completed"] is True
        
        # Get non-existent step result
        assert session.get_step_result("nonexistent") is None
        
        # Test with no workflow data
        session.workflow_data = None
        assert session.get_step_result("step1") is None
    
    def test_get_variable(self, session):
        """Test getting a workflow variable"""
        # Get existing variable
        assert session.get_variable("test_var") == "test_value"
        
        # Get non-existent variable with default
        assert session.get_variable("nonexistent", "default") == "default"
        
        # Test with no workflow data
        session.workflow_data = None
        assert session.get_variable("test_var", "default") == "default"
    
    def test_set_variable(self, session):
        """Test setting a workflow variable"""
        # Set a new variable
        session.set_variable("new_var", "new_value")
        assert session.workflow_data["variables"]["new_var"] == "new_value"
        
        # Update an existing variable
        session.set_variable("test_var", "updated_value")
        assert session.workflow_data["variables"]["test_var"] == "updated_value"
        
        # Test with no workflow data
        session.workflow_data = None
        session.set_variable("test_var", "value")
        assert session.workflow_data["variables"]["test_var"] == "value"
    
    def test_first_message(self, session_with_messages):
        """Test getting the first message in the session"""
        first_message = session_with_messages.first_message
        assert first_message is not None
        assert first_message.text == "First message"
        
        # Test with no messages
        session_with_messages.messages = []
        assert session_with_messages.first_message is None
