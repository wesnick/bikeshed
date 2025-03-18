import pytest
import uuid
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from src.models.models import Session, Message
from src.service.workflow import WorkflowService, on_message, on_prompt, on_user_input, on_invoke
from src.core.config_types import SessionTemplate, Step, MessageStep, PromptStep, UserInputStep, InvokeStep


@pytest.fixture
def session_template():
    """Create a sample session template with different step types"""
    return SessionTemplate(
        name="Test Template",
        description="A template for testing",
        model="test_model",
        steps=[
            MessageStep(
                name="welcome",
                type="message",
                role="system",
                content="Welcome to the test workflow",
                enabled=True
            ),
            PromptStep(
                name="question",
                type="prompt",
                content="What is your favorite color?",
                enabled=True
            ),
            UserInputStep(
                name="user_response",
                type="user_input",
                prompt="Please provide your input",
                enabled=True
            ),
            InvokeStep(
                name="process_data",
                type="invoke",
                callable="process_user_data",
                enabled=True
            )
        ]
    )


@pytest.fixture
def session(session_template):
    """Create a sample session with the test template"""
    return Session(
        id=uuid.uuid4(),
        description="Test Session",
        template=session_template,
        created_at=datetime.now(),
        status="pending",
        current_state="start",
        workflow_data={
            "current_step_index": 0,
            "step_results": {},
            "variables": {},
            "errors": []
        }
    )


class TestWorkflowService:
    
    @pytest.mark.asyncio
    async def test_initialize_session(self, session):
        """Test initializing a session with a workflow"""
        workflow_service = WorkflowService()
        
        # Initialize the session
        initialized_session = await workflow_service.initialize_session(session)
        
        # Verify the session has a state machine
        assert initialized_session.machine is not None
        
        # Verify the states are correctly set up
        assert 'start' in initialized_session.machine.states
        assert 'step0' in initialized_session.machine.states
        assert 'step1' in initialized_session.machine.states
        assert 'step2' in initialized_session.machine.states
        assert 'step3' in initialized_session.machine.states
        assert 'end' in initialized_session.machine.states
        
        # Verify the transitions are correctly set up
        assert hasattr(initialized_session, 'run_step0')
        assert hasattr(initialized_session, 'run_step1')
        assert hasattr(initialized_session, 'run_step2')
        assert hasattr(initialized_session, 'run_step3')
        
        # Verify the workflow data is initialized
        assert initialized_session.workflow_data['current_step_index'] == 0
        assert initialized_session.workflow_data['step_results'] == {}
        assert initialized_session.workflow_data['variables'] == {}
        assert initialized_session.workflow_data['errors'] == []
    
    @pytest.mark.asyncio
    async def test_get_next_step(self, session):
        """Test getting the next step in the workflow"""
        workflow_service = WorkflowService()
        
        # Test getting the first step
        next_step = await workflow_service.get_next_step(session)
        assert next_step is not None
        assert next_step.name == "welcome"
        assert next_step.type == "message"
        
        # Test getting the second step
        session.workflow_data['current_step_index'] = 1
        next_step = await workflow_service.get_next_step(session)
        assert next_step is not None
        assert next_step.name == "question"
        assert next_step.type == "prompt"
        
        # Test getting a step beyond the end
        session.workflow_data['current_step_index'] = 10
        next_step = await workflow_service.get_next_step(session)
        assert next_step is None
    
    @pytest.mark.asyncio
    @patch('src.service.workflow.persist_workflow')
    async def test_execute_next_step(self, mock_persist, session):
        """Test executing the next step in the workflow"""
        workflow_service = WorkflowService()
        await workflow_service.initialize_session(session)
        
        # Mock the trigger method
        session.run_step0 = AsyncMock()
        
        # Execute the next step
        result = await workflow_service.execute_next_step(session)
        
        # Verify the step was executed
        assert result is True
        session.run_step0.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.service.workflow.persist_workflow')
    async def test_provide_user_input(self, mock_persist, session):
        """Test providing user input for a user_input step"""
        workflow_service = WorkflowService()
        await workflow_service.initialize_session(session)
        
        # Set up the session to be waiting for input
        session.status = 'waiting_for_input'
        session.workflow_data['current_step_index'] = 2  # User input step
        
        # Mock the execute_next_step method
        workflow_service.execute_next_step = AsyncMock(return_value=True)
        
        # Provide user input
        result = await workflow_service.provide_user_input(session, "Blue")
        
        # Verify the input was stored and the step was executed
        assert result is True
        assert session.workflow_data['user_input'] == "Blue"
        workflow_service.execute_next_step.assert_called_once_with(session)


@pytest.mark.asyncio
async def test_on_message(session):
    """Test the on_message handler"""
    # Set up the event data
    event_data = MagicMock()
    event_data.model = session
    
    # Execute the handler
    with patch('src.service.workflow.WorkflowService.get_next_step') as mock_get_next_step:
        # Mock the next step
        mock_step = MessageStep(
            name="welcome",
            type="message",
            role="system",
            content="Welcome to the test workflow",
            enabled=True
        )
        mock_get_next_step.return_value = mock_step
        
        # Call the handler
        await on_message(event_data)
        
        # Verify the session was updated
        assert session.status == 'running'
        assert len(session._temp_messages) == 1
        assert session._temp_messages[0].role == "system"
        assert session._temp_messages[0].text == "Welcome to the test workflow"
        assert session.workflow_data['current_step_index'] == 1
        assert session.workflow_data['step_results']['welcome']['completed'] is True


@pytest.mark.asyncio
async def test_on_prompt(session):
    """Test the on_prompt handler"""
    # Set up the event data
    event_data = MagicMock()
    event_data.model = session
    
    # Execute the handler
    with patch('src.service.workflow.WorkflowService.get_next_step') as mock_get_next_step:
        # Mock the next step
        mock_step = PromptStep(
            name="question",
            type="prompt",
            content="What is your favorite color?",
            enabled=True
        )
        mock_get_next_step.return_value = mock_step
        
        # Call the handler
        await on_prompt(event_data)
        
        # Verify the session was updated
        assert session.status == 'running'
        assert len(session._temp_messages) == 2  # User message and assistant response
        assert session._temp_messages[0].role == "user"
        assert session._temp_messages[0].text == "What is your favorite color?"
        assert session._temp_messages[1].role == "assistant"
        assert "LLM response for prompt" in session._temp_messages[1].text
        assert session.workflow_data['current_step_index'] == 1
        assert session.workflow_data['step_results']['question']['completed'] is True


@pytest.mark.asyncio
async def test_on_user_input(session):
    """Test the on_user_input handler"""
    # Set up the event data
    event_data = MagicMock()
    event_data.model = session
    
    # Execute the handler
    with patch('src.service.workflow.WorkflowService.get_next_step') as mock_get_next_step:
        # Mock the next step
        mock_step = UserInputStep(
            name="user_response",
            type="user_input",
            prompt="Please provide your input",
            enabled=True
        )
        mock_get_next_step.return_value = mock_step
        
        # Call the handler
        await on_user_input(event_data)
        
        # Verify the session was updated
        assert session.status == 'waiting_for_input'
        assert len(session._temp_messages) == 1
        assert session._temp_messages[0].role == "user"
        assert session._temp_messages[0].text == "Sample user input"
        assert session.workflow_data['current_step_index'] == 1
        assert session.workflow_data['step_results']['user_response']['completed'] is True


@pytest.mark.asyncio
async def test_on_invoke(session):
    """Test the on_invoke handler"""
    # Set up the event data
    event_data = MagicMock()
    event_data.model = session
    
    # Execute the handler
    with patch('src.service.workflow.WorkflowService.get_next_step') as mock_get_next_step:
        # Mock the next step
        mock_step = InvokeStep(
            name="process_data",
            type="invoke",
            callable="process_user_data",
            enabled=True
        )
        mock_get_next_step.return_value = mock_step
        
        # Call the handler
        await on_invoke(event_data)
        
        # Verify the session was updated
        assert session.status == 'running'
        assert session.workflow_data['current_step_index'] == 1
        assert session.workflow_data['step_results']['process_data']['completed'] is True
        assert "Result of invoking process_user_data" in session.workflow_data['step_results']['process_data']['result']


@pytest.mark.asyncio
@patch('src.dependencies.get_db')
@patch('src.repository.session_repository.update')
@patch('src.repository.session_repository.get_by_id')
async def test_persist_workflow(mock_get_by_id, mock_update, mock_get_db, session):
    """Test persisting workflow state to the database"""
    # Set up the session and event data
    session.machine = MagicMock()
    session.machine.get_model_state.return_value.name = 'step1'
    session._temp_messages = [
        Message(
            id=uuid.uuid4(),
            session_id=session.id,
            role="system",
            text="Test message",
            status="delivered"
        )
    ]
    
    # Mock session repository to return the session
    mock_get_by_id.return_value = session
    
    event_data = MagicMock()
    event_data.model = session
    event_data.event.name = 'run_step0'
    
    # Mock the database session
    db = AsyncMock()
    db.commit = AsyncMock()
    mock_get_db.return_value.__aiter__.return_value = [db]
    
    # Call the persist_workflow function
    from src.service.workflow import persist_workflow
    await persist_workflow(event_data)
    
    # Verify the database was updated
    mock_update.assert_called_once_with(
        db,
        session.id,
        {
            'status': session.status,
            'current_state': 'step1',
            'workflow_data': session.workflow_data
        }
    )
    assert db.add.call_count == 1  # One message was added
    assert db.commit.call_count == 1
    assert session._temp_messages == []  # Messages were cleared
