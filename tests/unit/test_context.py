import os
import pytest
import json
from app.context.manager import ContextManager

def test_context_lifecycle(tmp_path):
    storage = tmp_path / "context.json"
    manager = ContextManager(storage_path=str(storage))
    
    assert manager.current_context.interview.role == ""
    
    manager.update_interview(role="Python Developer", technology_stack=["Python", "FastAPI"])
    assert manager.current_context.interview.role == "Python Developer"
    assert "FastAPI" in manager.current_context.interview.technology_stack
    
    # test save and load
    manager2 = ContextManager(storage_path=str(storage))
    assert manager2.current_context.interview.role == "Python Developer"
    
    manager2.reset()
    assert manager2.current_context.interview.role == ""
    
def test_context_corrupted(tmp_path):
    storage = tmp_path / "context.json"
    storage.write_text("invalid json")
    
    manager = ContextManager(storage_path=str(storage))
    assert manager.current_context.interview.role == ""

def test_system_prompt_addition(tmp_path):
    manager = ContextManager(storage_path=str(tmp_path / "context.json"))
    manager.update_interview(role="SWE")
    prompt = manager.build_system_prompt_addition()
    assert "--- INTERVIEW CONTEXT ---" in prompt
    assert "Role: SWE" in prompt
    
    manager.reset()
    assert manager.build_system_prompt_addition() == ""
