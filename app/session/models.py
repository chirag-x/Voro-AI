from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import uuid
import time
from enum import Enum

class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class SessionState(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    ENDED = "ended"

class ConversationTurn(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: Role
    text: str
    timestamp: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    turns: List[ConversationTurn] = Field(default_factory=list)
    state: SessionState = SessionState.IDLE
