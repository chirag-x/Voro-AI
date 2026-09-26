import pytest
import httpx
from app.ai.openrouter import OpenRouterProvider
from app.session.models import ConversationTurn, Role

class MockResponse:
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
        
    def json(self):
        return self.json_data
        
    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "url")
            raise httpx.HTTPStatusError("Error", request=request, response=self)

def test_openrouter_success(monkeypatch):
    def mock_post(*args, **kwargs):
        return MockResponse({
            "id": "req-123",
            "model": "google/gemini-2.5-flash-lite",
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"total_tokens": 10}
        })
        
    monkeypatch.setattr(httpx.Client, "post", mock_post)
    
    provider = OpenRouterProvider("fake_key", "fake_model", "http://fake")
    context = [ConversationTurn(role=Role.USER, text="Hi")]
    
    resp = provider.generate(context, "System prompt")
    assert resp.text == "Hello!"
    assert resp.model == "google/gemini-2.5-flash-lite"
    assert resp.request_id == "req-123"

def test_openrouter_missing_key():
    provider = OpenRouterProvider("", "fake", "fake")
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY is missing"):
        provider.generate([], "sys")

def test_openrouter_http_error(monkeypatch):
    def mock_post(*args, **kwargs):
        return MockResponse({}, status_code=401)
        
    monkeypatch.setattr(httpx.Client, "post", mock_post)
    
    provider = OpenRouterProvider("fake", "fake", "http://fake")
    with pytest.raises(httpx.HTTPStatusError):
        provider.generate([], "sys")
