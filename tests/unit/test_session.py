import pytest
from app.session.manager import SessionManager
from app.session.models import Role, SessionState

def test_session_lifecycle():
    manager = SessionManager(max_turns=3)
    assert manager.current_session.state == SessionState.IDLE
    
    manager.start_session()
    assert manager.current_session.state == SessionState.ACTIVE
    
    manager.end_session()
    assert manager.current_session.state == SessionState.ENDED

def test_add_turns():
    manager = SessionManager(max_turns=5)
    
    manager.add_user_turn("Hello")
    assert manager.current_session.state == SessionState.ACTIVE
    
    manager.add_assistant_turn("Hi there")
    
    context = manager.get_context()
    assert len(context) == 2
    assert context[0].role == Role.USER
    assert context[0].text == "Hello"
    assert context[1].role == Role.ASSISTANT
    assert context[1].text == "Hi there"

def test_context_limits():
    manager = SessionManager(max_turns=2)
    
    manager.add_user_turn("1")
    manager.add_user_turn("2")
    manager.add_user_turn("3")
    
    context = manager.get_context()
    assert len(context) == 2
    assert context[0].text == "2"
    assert context[1].text == "3"

def test_reset_session():
    manager = SessionManager()
    manager.add_user_turn("Hello")
    session_id1 = manager.current_session.session_id
    
    manager.reset_session()
    assert len(manager.get_context()) == 0
    assert manager.current_session.session_id != session_id1
    assert manager.current_session.state == SessionState.IDLE
