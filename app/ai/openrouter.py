import time
import httpx
from typing import List
from app.ai.provider import AIProvider
from app.ai.models import AIResponse
from app.session.models import ConversationTurn, Role
from app.utils.logging import logger

class OpenRouterProvider(AIProvider):
    def __init__(self, api_key: str, model: str, base_url: str):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def switch_model(self, new_model: str):
        """Hot-swap the model without restarting."""
        logger.info(f"[ai] Switching model: {self.model} → {new_model}")
        self.model = new_model
        
    def generate(self, context: List[ConversationTurn], system_prompt: str, base64_image: str = None) -> AIResponse:
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is missing or empty.")
            
        start_time = time.time()
        
        messages = [{"role": "system", "content": system_prompt}]
        for i, turn in enumerate(context):
            # If this is the last turn and we have an image, append it as a multimodal block
            if i == len(context) - 1 and base64_image:
                messages.append({
                    "role": turn.role.value,
                    "content": [
                        {"type": "text", "text": turn.text},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]
                })
            else:
                messages.append({"role": turn.role.value, "content": turn.text})
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/Voro",
            "X-Title": "Voro Desktop Assistant"
        }
        
        # Dynamically load temperature based on tone
        from app.core.config import load_config
        cfg = load_config()
        tone = getattr(cfg, 'ai_tone', 'Conversational (Script)')
        
        # Human-like needs higher temp (0.7). Code Only needs low temp (0.1).
        if tone in ["Conversational (Script)", "Conversational Hinglish (Script)"]:
            temp = 0.7
        elif tone == "Code Only":
            temp = 0.1
        else:
            temp = 0.4
            
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temp
        }
        
        logger.info(f"[ai] Sending request to OpenRouter ({self.model})...")
        
        def _do_post(req_payload):
            response = self.client.post(f"{self.base_url}/chat/completions", headers=headers, json=req_payload)
            if response.status_code == 400 and base64_image:
                raise ValueError("VISION_NOT_SUPPORTED")
            response.raise_for_status()
            return response
            
        try:
            response = _do_post(payload)
        except ValueError as e:
            if str(e) == "VISION_NOT_SUPPORTED":
                logger.warning(f"[ai] Model {self.model} rejected vision payload (400 Bad Request). Retrying with text-only.")
                text_messages = [{"role": "system", "content": system_prompt}]
                for turn in context:
                    text_messages.append({"role": turn.role.value, "content": turn.text})
                payload["messages"] = text_messages
                response = _do_post(payload)
            else:
                raise
        except httpx.HTTPStatusError as e:
            logger.error(f"[ai] OpenRouter HTTP Error {e.response.status_code}")
            raise
        except httpx.RequestError as e:
            logger.error(f"[ai] OpenRouter Request Error: {str(e)}")
            raise
            
        data = response.json()
        if "choices" not in data or not data["choices"]:
            raise ValueError("Unexpected API response structure (no choices)")
            
        text = data["choices"][0]["message"].get("content")
        if text is None:
            text = ""
        usage = data.get("usage")
        request_id = data.get("id")
        
        processing_time = time.time() - start_time
        logger.info("[ai] Response received")
        
        return AIResponse(
            text=text,
            model=data.get("model", self.model),
            usage=usage,
            request_id=request_id,
            processing_time=processing_time
        )
        
    def generate_stream(self, context: List[ConversationTurn], system_prompt: str, base64_image: str = None):
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is missing or empty.")
            
        messages = [{"role": "system", "content": system_prompt}]
        for i, turn in enumerate(context):
            # If this is the last turn and we have an image, append it as a multimodal block
            if i == len(context) - 1 and base64_image:
                messages.append({
                    "role": turn.role.value,
                    "content": [
                        {"type": "text", "text": turn.text},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]
                })
            else:
                messages.append({"role": turn.role.value, "content": turn.text})
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/Voro",
            "X-Title": "Voro Desktop Assistant"
        }
        
        from app.core.config import load_config
        cfg = load_config()
        tone = getattr(cfg, 'ai_tone', 'Conversational (Script)')
        temp = 0.7 if tone in ["Conversational (Script)", "Conversational Hinglish (Script)"] else (0.1 if tone == "Code Only" else 0.4)
            
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temp,
            "stream": True
        }
        
        import json
        logger.info(f"[ai] Sending streaming request to OpenRouter ({self.model})...")
        
        def _do_stream(req_payload):
            with self.client.stream("POST", f"{self.base_url}/chat/completions", headers=headers, json=req_payload) as response:
                if response.status_code == 400 and base64_image:
                    # Model likely doesn't support vision
                    raise ValueError("VISION_NOT_SUPPORTED")
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            data = json.loads(line[6:])
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            pass
                            
        try:
            yield from _do_stream(payload)
        except ValueError as e:
            if str(e) == "VISION_NOT_SUPPORTED":
                logger.warning(f"[ai] Model {self.model} rejected vision payload (400 Bad Request). Retrying with text-only.")
                # Rebuild messages without image
                text_messages = [{"role": "system", "content": system_prompt}]
                for turn in context:
                    text_messages.append({"role": turn.role.value, "content": turn.text})
                payload["messages"] = text_messages
                yield from _do_stream(payload)
            else:
                raise
