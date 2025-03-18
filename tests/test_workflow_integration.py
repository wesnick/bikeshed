import pytest
import uuid
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from src.models.models import Session
from src.service.workflow import WorkflowService
from src.core.config_types import SessionTemplate, MessageStep, PromptStep, UserInputStep, InvokeStep


@pytest.fixture
def complex_session_template():
    """Create a more complex session template for integration testing"""
    return SessionTemplate(
        name="Complex Test Template",
        description="A complex template for integration testing",
        steps=[
            MessageStep(
                name="welcome",
                type="message",
                role="system",
                content="Welcome to the integration test",
                enabled=True
            ),
            PromptStep(
                name="initial_question",
                type="prompt",
                content="What would you like to test today?",
                enabled=True
            ),
            UserInputStep(
                name="user_choice",
                type="user_input",
                prompt="Please select a test option",
                enabled=True
            ),
            InvokeStep(
                name="process_choice",
                type="invoke",
                callable="process_user_choice",
                enabled=True
            ),
            MessageStep(
                name="conclusion",
                type="message",
                role="system",
                content="Thank you for testing!",
                enabled=True
            )
        ]
    )


@pytest.fixture
def complex_session(complex_session_template):
    """Create a session with the complex template"""
    return Session(
        id=uuid.uuid4(),
        description="Integration Test Session",
        template=complex_session_template,
        created_at=datetime.now(),
        status="pending",
        current_state="start",
        workflow_data=None  # Will be initialized by the workflow service
    )


class TestWorkflowIntegration:
    
    @pytest.mark.asyncio
    @patch('src.service.workflow.persist_workflow')
    async def test_full_workflow_execution(self, mock_persist, complex_session):
        """Test executing a full workflow from start to end"""
        workflow_service = WorkflowService()
        
        # Initialize the session
        await workflow_service.initialize_session(complex_session)
        
        # Verify initial state
        assert complex_session.current_state == 'start'
        assert complex_session.workflow_data['current_step_index'] == 0
        
        # Execute the welcome message step
        with patch('src.service.workflow.on_message', new_callable=AsyncMock) as mock_on_message:
            await workflow_service.execute_next_step(complex_session)
            mock_on_message.assert_called_once()
        
        # Execute the prompt step
        with patch('src.service.workflow.on_prompt', new_callable=AsyncMock) as mock_on_prompt:
            complex_session.workflow_data['current_step_index'] = 1
            await workflow_service.execute_next_step(complex_session)
            mock_on_prompt.assert_called_once()
        
        # Execute the user input step
        with patch('src.service.workflow.on_user_input', new_callable=AsyncMock) as mock_on_user_input:
            complex_session.workflow_data['current_step_index'] = 2
            await workflow_service.execute_next_step(complex_session)
            mock_on_user_input.assert_called_once()
        
        # Provide user input
        with patch.object(workflow_service, 'execute_next_step', new_callable=AsyncMock) as mock_execute:
            complex_session.status = 'waiting_for_input'
            await workflow_service.provide_user_input(complex_session, "Option A")
            assert complex_session.workflow_data['user_input'] == "Option A"
            mock_execute.assert_called_once_with(complex_session)
        
        # Execute the invoke step
        with patch('src.service.workflow.on_invoke', new_callable=AsyncMock) as mock_on_invoke:
            complex_session.workflow_data['current_step_index'] = 3
            await workflow_service.execute_next_step(complex_session)
            mock_on_invoke.assert_called_once()
        
        # Execute the conclusion message step
        with patch('src.service.workflow.on_message', new_callable=AsyncMock) as mock_on_message:
            complex_session.workflow_data['current_step_index'] = 4
            await workflow_service.execute_next_step(complex_session)
            mock_on_message.assert_called_once()
        
        # Verify the workflow is complete
        complex_session.workflow_data['current_step_index'] = 5
        assert complex_session.is_complete() is True
    
    @pytest.mark.asyncio
    @patch('src.service.workflow.persist_workflow')
    async def test_workflow_with_disabled_steps(self, mock_persist, complex_session_template, complex_session):
        """Test workflow execution with disabled steps"""
        # Disable some steps
        complex_session_template.steps[1].enabled = False  # Disable the prompt step
        complex_session_template.steps[3].enabled = False  # Disable the invoke step
        complex_session.template = complex_session_template
        
        workflow_service = WorkflowService()
        
        # Initialize the session
        await workflow_service.initialize_session(complex_session)
        
        # Verify the states - should only have start, step0, step2, step4, end
        assert 'start' in complex_session.machine.states
        assert 'step0' in complex_session.machine.states
        assert 'step2' in complex_session.machine.states
        assert 'step4' in complex_session.machine.states
        assert 'end' in complex_session.machine.states
        
        # Verify the transitions - should only have run_step0, run_step2, run_step4
        assert hasattr(complex_session, 'run_step0')
        assert hasattr(complex_session, 'run_step2')
        assert hasattr(complex_session, 'run_step4')
        assert not hasattr(complex_session, 'run_step1')
        assert not hasattr(complex_session, 'run_step3')
    
    @pytest.mark.asyncio
    @patch('src.service.workflow.persist_workflow')
    async def test_error_handling(self, mock_persist, complex_session):
        """Test error handling during workflow execution"""
        workflow_service = WorkflowService()
        
        # Initialize the session
        await workflow_service.initialize_session(complex_session)
        
        # Simulate an error during step execution
        with patch('src.service.workflow.on_message', side_effect=Exception("Test error")):
            # This should not raise an exception but log the error
            with pytest.raises(Exception, match="Test error"):
                await workflow_service.execute_next_step(complex_session)
