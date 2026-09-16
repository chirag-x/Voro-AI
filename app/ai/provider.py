from typing import List, Dict, Any
from app.ai.models import AIResponse
from app.session.models import ConversationTurn

class AIProvider:
    """Abstract interface for AI Providers."""
    
    def generate(self, context: List[ConversationTurn], system_prompt: str, base64_image: str = None) -> AIResponse:
        """Generate a response based on the conversation context."""
        raise NotImplementedError("Must be implemented by subclass")

    def generate_stream(self, context: List[ConversationTurn], system_prompt: str, base64_image: str = None):
        """Yield chunks of text as they are generated."""
        raise NotImplementedError("Must be implemented by subclass")
