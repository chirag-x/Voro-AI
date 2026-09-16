from pydantic import BaseModel
from typing import Optional

class TranscriptResult(BaseModel):
    text: str
    language: str
    confidence: Optional[float] = None
    duration: Optional[float] = None
    processing_time: Optional[float] = None
