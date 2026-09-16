from pydantic import BaseModel
from typing import List
from app.session.models import ConversationTurn

class ContextRequirements(BaseModel):
    session: bool = True
    interview_context: bool = True
    screen: bool = False
    ocr: bool = False
    coding: bool = False

class IntelligenceRouter:
    def __init__(self):
        # Screen is ONLY needed when the user refers to something visible on screen
        self.screen_signals = [
            "this", "here", "on screen", "look at", "wrong with",
            "explain this", "what is this", "on my screen", "i see",
            "the screen", "this code", "this error", "this problem",
            "this question", "on the screen", "shown here", "above",
            "leetcode", "hackerrank", "codeforces"
        ]
        
        # Coding signals → use coding model but DON'T grab the screen
        self.coding_signals = [
            "code", "function", "implement", "algorithm", "class",
            "write a", "write me", "give me", "create a", "build a",
            "bug", "traceback", "syntax", "debug", "fix this", "refactor",
            "complexity", "big o", "data structure", "recursion", "loop"
        ]

    def route(self, intent: str, user_text: str, context: List[ConversationTurn]) -> ContextRequirements:
        text_lower = user_text.lower()
        
        # Audio-only commands
        if intent == "COMMAND":
            return ContextRequirements(session=False, interview_context=False, screen=False, ocr=False, coding=False)
            
        # Auto-monitor triggered — always needs screen
        if intent == "SCREEN_UPDATE":
            return ContextRequirements(session=True, interview_context=True, screen=True, ocr=True, coding=True)
            
        reqs = ContextRequirements()
        
        needs_screen = any(sig in text_lower for sig in self.screen_signals)
        needs_coding = any(sig in text_lower for sig in self.coding_signals)
        
        # Screen grab ONLY when user explicitly references on-screen content
        if needs_screen:
            reqs.screen = True
            reqs.ocr = True
            reqs.coding = True  # screen questions are always coding-adjacent
        elif needs_coding:
            # Pure coding question — use coding model but skip expensive OCR
            reqs.screen = False
            reqs.ocr = False
            reqs.coding = True
            
        # If question references earlier context, don't re-grab screen
        if "earlier" in text_lower or "previous" in text_lower or "you said" in text_lower:
            reqs.screen = False
            reqs.ocr = False
            
        return reqs
