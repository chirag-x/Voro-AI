from pydantic import BaseModel, Field
from typing import Optional, Dict
import time
import uuid

class PipelineTrace(BaseModel):
    stt_ms: float = 0
    routing_ms: float = 0
    capture_ms: float = 0
    ocr_ms: float = 0
    analysis_ms: float = 0
    context_ms: float = 0
    llm_ms: float = 0
    overlay_ms: float = 0
    
    @property
    def total_ms(self) -> float:
        return self.stt_ms + self.routing_ms + self.capture_ms + self.ocr_ms + self.analysis_ms + self.context_ms + self.llm_ms + self.overlay_ms

class PipelineRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: f"REQ-{uuid.uuid4().hex[:8].upper()}")
    text: str
    intent: str
    timestamp: float = Field(default_factory=time.time)
    trace: PipelineTrace = Field(default_factory=PipelineTrace)
