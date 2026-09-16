import re
from app.intent.models import IntentResult, Intent, IntentSource

class IntentDetector:
    def __init__(self):
        # Commands — matched as substrings so "clear session" / "voro clear session" all work
        self.command_phrases = [
            "start listening", "stop listening",
            "reset session", "clear session", "clear conversation",
            "clear memory", "clear chat", "wipe memory", "forget everything",
            "new session", "fresh start",
            "sleep", "wake up",
            "exit voro", "exit", "quit", "close voro", "close application", "shut down"
        ]
        
        self.question_words = {
            "what", "why", "how", "when", "where", "who", "which", "explain", "describe", "could you", "can you", "would you"
        }
        
        self.conversation_phrases = {
            "hello", "hi", "hey", "thanks", "thank you", "okay", "ok", "cool", "awesome", "good", "makes sense"
        }

    def detect(self, text: str) -> IntentResult:
        normalized = text.lower().strip()
        # Remove punctuation for matching
        clean_text = re.sub(r'[^\w\s]', '', normalized)
        
        # 1. Command detection — substring match so variations like "clear session" all hit
        for phrase in self.command_phrases:
            if phrase in clean_text:
                return IntentResult(
                    intent=Intent.COMMAND,
                    confidence=1.0,
                    source=IntentSource.RULE,
                    normalized_text=normalized
                )
            
        # 2. Conversation detection (exact or highly similar)
        if clean_text in self.conversation_phrases:
            return IntentResult(
                intent=Intent.CONVERSATION,
                confidence=0.9,
                source=IntentSource.RULE,
                normalized_text=normalized
            )
            
        # 3. Question detection (heuristic)
        # Ends with question mark or starts with question word
        if normalized.endswith("?"):
            return IntentResult(
                intent=Intent.QUESTION,
                confidence=0.9,
                source=IntentSource.RULE,
                normalized_text=normalized
            )
            
        first_word = clean_text.split(" ")[0] if clean_text else ""
        if first_word in self.question_words or any(clean_text.startswith(q + " ") for q in self.question_words):
            return IntentResult(
                intent=Intent.QUESTION,
                confidence=0.8,
                source=IntentSource.RULE,
                normalized_text=normalized
            )
            
        # If it's short and we don't know, it's UNKNOWN. 
        # But if it's long, it might be a statement/conversation. We default to QUESTION if we're not sure,
        # or maybe UNKNOWN to let LLM decide. The instructions say "this is something unclear -> UNKNOWN".
        return IntentResult(
            intent=Intent.UNKNOWN,
            confidence=0.5,
            source=IntentSource.RULE,
            normalized_text=normalized
        )
