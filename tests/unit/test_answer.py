import pytest
from app.answer.engine import AnswerEngine
from app.answer.models import AnswerMode
from app.context.manager import ContextManager
from app.ai.provider import AIProvider
from app.ai.models import AIResponse
from app.session.models import ConversationTurn, Role

class MockAIProvider(AIProvider):
    def generate(self, context, system_prompt):
        return AIResponse(text="Mock Answer", model="mock", processing_time=0.1)

def test_answer_mode_selection(tmp_path):
    ctx_mgr = ContextManager(storage_path=str(tmp_path / "c.json"))
    engine = AnswerEngine(MockAIProvider(), ctx_mgr)
    
    # Empty context
    res = engine.generate_answer("QUESTION", [])
    assert not res.success
    
    # Technical
    turns = [ConversationTurn(role=Role.USER, text="what is polymorphism")]
    res = engine.generate_answer("QUESTION", turns)
    assert res.answer_mode == AnswerMode.TECHNICAL
    
    # Coding
    turns = [ConversationTurn(role=Role.USER, text="implement a binary search")]
    res = engine.generate_answer("COMMAND", turns)
    assert res.answer_mode == AnswerMode.CODING
    
    # Follow-up
    turns = [
        ConversationTurn(role=Role.USER, text="what is a stack"),
        ConversationTurn(role=Role.ASSISTANT, text="a stack is LIFO"),
        ConversationTurn(role=Role.USER, text="why use it")
    ]
    res = engine.generate_answer("QUESTION", turns)
    assert res.answer_mode == AnswerMode.FOLLOW_UP
    
    # Interview (has context + question)
    ctx_mgr.update_interview(role="SWE")
    turns = [ConversationTurn(role=Role.USER, text="what is a stack")]
    res = engine.generate_answer("QUESTION", turns)
    assert res.answer_mode == AnswerMode.INTERVIEW

def test_answer_generation(tmp_path):
    ctx_mgr = ContextManager(storage_path=str(tmp_path / "c.json"))
    engine = AnswerEngine(MockAIProvider(), ctx_mgr)
    turns = [ConversationTurn(role=Role.USER, text="Hello")]
    res = engine.generate_answer("CONVERSATION", turns)
    
    assert res.success
    assert res.answer_text == "Mock Answer"
    assert res.latency > 0
