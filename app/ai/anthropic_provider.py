import time
import httpx
from typing import List
import json

from app.ai.provider import AIProvider
from app.ai.models import AIResponse
from app.session.models import ConversationTurn, Role
from app.utils.logging import logger

class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str, model: str, base_url: str = "https://api.anthropic.com/v1/messages"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def switch_model(self, new_model: str):
        logger.info(f"[ai] Switching Anthropic model: {self.model} → {new_model}")
        self.model = new_model
        
    def generate(self, context: List[ConversationTurn], system_prompt: str, base64_image: str = None) -> AIResponse:
        if not self.api_key:
            raise ValueError("Anthropic API key is missing.")
            
        start_time = time.time()
        
        # Anthropic messages API does not accept "system" role in the messages array.
        messages = []
        for i, turn in enumerate(context):
            role = "assistant" if turn.role == Role.ASSISTANT else "user"
            
            # If this is the last turn and we have an image, format for Anthropic vision
            if i == len(context) - 1 and base64_image:
                messages.append({
                    "role": role,
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64_image}},
                        {"type": "text", "text": turn.text}
                    ]
                })
            else:
                messages.append({"role": role, "content": turn.text})
            
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        from app.core.config import load_config
        cfg = load_config()
        tone = getattr(cfg, 'ai_tone', 'Conversational (Script)')
        
        if tone in ["Conversational (Script)", "Conversational Hinglish (Script)"]:
            temp = 0.7
        elif tone == "Code Only":
            temp = 0.1
        else:
            temp = 0.4
            
        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": messages,
            "temperature": temp,
            "max_tokens": 4096
        }
        
        try:
            logger.info(f"[ai] Sending Anthropic payload. Model={self.model}")
            r = self.client.post(self.base_url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            
            text = ""
            if "content" in data and len(data["content"]) > 0:
                text = data["content"][0].get("text", "")
            
            usage = data.get("usage", {})
            prompt_tokens = usage.get("input_tokens", 0)
            comp_tokens = usage.get("output_tokens", 0)
            
            return AIResponse(
                text=text,
                prompt_tokens=prompt_tokens,
                completion_tokens=comp_tokens,
                latency_sec=time.time() - start_time
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"[ai] Anthropic HTTP Error: {e.response.text}")
            return AIResponse(text=f"[API Error] {e.response.text}", latency_sec=time.time() - start_time)
        except Exception as e:
            logger.error(f"[ai] Anthropic Error: {str(e)}")
            return AIResponse(text=f"[Error] {str(e)}", latency_sec=time.time() - start_time)
