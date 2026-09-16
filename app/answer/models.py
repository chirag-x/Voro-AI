from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional

class AnswerMode(str, Enum):
    GENERAL = "GENERAL"
    INTERVIEW = "INTERVIEW"
    TECHNICAL = "TECHNICAL"
    CODING = "CODING"
    FOLLOW_UP = "FOLLOW_UP"

class AnswerRequest(BaseModel):
    user_text: str
    intent: str
    session_turns: int
    has_context: bool

class AnswerResult(BaseModel):
    success: bool
    answer_text: str
    answer_mode: AnswerMode
    latency: float = 0.0
    error: Optional[str] = None
