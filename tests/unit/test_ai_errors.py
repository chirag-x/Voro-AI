import pytest
import time
import queue
from unittest.mock import MagicMock
from app.core.application import VoroApplication
from app.core.models import PipelineRequest
from app.answer.models import AnswerResult

@pytest.fixture
def mock_app():
    app = VoroApplication()
    
    # Mock dependencies
    app.session_manager = MagicMock()
    app.intelligence_router = MagicMock()
    app.answer_engine = MagicMock()
    app.mm_engine = MagicMock()
    
    # Mock callbacks
    app.on_answer_callback = MagicMock()
    app.on_error_callback = MagicMock()
    app.on_processing_state_callback = MagicMock()
    
    # Setup test request
    app.latest_request_id = "test-123"
    req = PipelineRequest(text="What is Python?", intent="QUESTION")
    req.request_id = "test-123"
    app.ai_queue.put(req)
    
    # Ensure worker stops immediately after processing one item
    app._pipeline_running = True
    
    # We patch queue.get to raise Empty after the first yield to exit loop cleanly
    orig_get = app.ai_queue.get
    def side_effect(*args, **kwargs):
        if not app.ai_queue.empty():
            return orig_get(*args, **kwargs)
        app._pipeline_running = False
        raise queue.Empty()
    app.ai_queue.get = side_effect
    
    return app, req

def test_successful_ai_response(mock_app):
    app, req = mock_app
    
    # Setup success response
    mock_result = AnswerResult(success=True, answer_text="Python is a language.", answer_mode="GENERAL")
    app.answer_engine.generate_answer.return_value = mock_result
    app.intelligence_router.route.return_value = MagicMock(screen=False)
    
    # Run worker
    app._ai_worker()
    
    # Verify behavior
    app.session_manager.add_assistant_turn.assert_called_once_with("Python is a language.")
    app.on_answer_callback.assert_called_once_with("Python is a language.")
    app.on_error_callback.assert_not_called()
    app.on_processing_state_callback.assert_any_call("IDLE")

def test_openrouter_429_fallback(mock_app):
    app, req = mock_app
    
    # Setup 429 response
    mock_result = AnswerResult(success=False, answer_text="I couldn't reach the AI service right now due to rate limiting (HTTP 429). Please try again shortly.", answer_mode="GENERAL")
    app.answer_engine.generate_answer.return_value = mock_result
    app.intelligence_router.route.return_value = MagicMock(screen=False)
    
    # Run worker
    app._ai_worker()
    
    # Verify behavior
    app.session_manager.add_assistant_turn.assert_not_called()  # Do not pollute session
    app.on_answer_callback.assert_not_called()
    app.on_error_callback.assert_called_once_with(mock_result.answer_text)
    app.on_processing_state_callback.assert_any_call("IDLE")

def test_unexpected_ai_exception(mock_app):
    app, req = mock_app
    
    # Setup exception in routing/answer engine directly
    app.answer_engine.generate_answer.side_effect = Exception("Unexpected connection drop")
    app.intelligence_router.route.return_value = MagicMock(screen=False)
    
    # Run worker
    app._ai_worker()
    
    # Verify behavior
    app.session_manager.add_assistant_turn.assert_not_called()
    app.on_answer_callback.assert_not_called()
    app.on_error_callback.assert_called_once_with("I encountered an internal error processing that request.")
    app.on_processing_state_callback.assert_any_call("IDLE")

def test_stale_request_isolation(mock_app):
    app, req = mock_app
    
    # Setup state where req is stale
    app.latest_request_id = "test-999"  # A newer request arrived
    
    # Run worker
    app._ai_worker()
    
    # Verify behavior: it should skip processing
    app.intelligence_router.route.assert_not_called()
    app.answer_engine.generate_answer.assert_not_called()

def test_recovery_after_429():
    app = VoroApplication()
    app.session_manager = MagicMock()
    app.intelligence_router = MagicMock()
    app.answer_engine = MagicMock()
    app.mm_engine = MagicMock()
    app.on_answer_callback = MagicMock()
    app.on_error_callback = MagicMock()
    app.on_processing_state_callback = MagicMock()
    
    req1 = PipelineRequest(text="Q1", intent="QUESTION")
    req2 = PipelineRequest(text="Q2", intent="QUESTION")
    
    app.ai_queue.put(req1)
    app.ai_queue.put(req2)
    app._pipeline_running = True
    
    # Mock processing
    responses = [
        AnswerResult(success=False, answer_text="429 error", answer_mode="GENERAL"),
        AnswerResult(success=True, answer_text="Success answer", answer_mode="GENERAL")
    ]
    
    def side_effect(*args, **kwargs):
        if not app.ai_queue.empty():
            req = app.ai_queue.queue[0]
            app.latest_request_id = req.request_id
            return orig_get(*args, **kwargs)
        app._pipeline_running = False
        raise queue.Empty()
        
    orig_get = app.ai_queue.get
    app.ai_queue.get = side_effect
    app.answer_engine.generate_answer.side_effect = responses
    app.intelligence_router.route.return_value = MagicMock(screen=False)
    
    app._ai_worker()
    
    app.on_error_callback.assert_called_once_with("429 error")
    app.on_answer_callback.assert_called_once_with("Success answer")
    assert app.on_processing_state_callback.call_count >= 2
    app.on_processing_state_callback.assert_any_call("IDLE")
