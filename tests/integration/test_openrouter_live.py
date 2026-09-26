import pytest
import os
from app.ai.openrouter import OpenRouterProvider
from app.session.models import ConversationTurn, Role
from app.core.config import load_config

def test_openrouter_live():
    config = load_config()
    if not config.openrouter_api_key:
        pytest.skip("Live OpenRouter test skipped: OPENROUTER_API_KEY not configured")
        
    provider = OpenRouterProvider(
        api_key=config.openrouter_api_key,
        model=config.openrouter_model,
        base_url=config.openrouter_base_url
    )
    
    context = [ConversationTurn(role=Role.USER, text="Hello, reply with exactly the word 'PONG'.")]
    
    try:
        response = provider.generate(context, "System prompt")
        assert response.text is not None
        assert "PONG" in response.text.upper()
    except Exception as e:
        if "429" in str(e):
            pytest.skip(f"OpenRouter API rate limited (429): {e}")
        else:
            pytest.fail(f"Live API call failed: {e}")
