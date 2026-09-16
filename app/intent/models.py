from enum import Enum
from pydantic import BaseModel
from typing import Optional

class Intent(str, Enum):
    QUESTION = "QUESTION"
    COMMAND = "COMMAND"
    CONVERSATION = "CONVERSATION"
    UNKNOWN = "UNKNOWN"

class IntentSource(str, Enum):
    RULE = "RULE"
    MODEL = "MODEL"
    UNKNOWN = "UNKNOWN"

class IntentResult(BaseModel):
    intent: Intent
    confidence: Optional[float] = None
    source: IntentSource
    normalized_text: str
