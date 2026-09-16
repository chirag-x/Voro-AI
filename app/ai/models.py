from pydantic import BaseModel
from typing import Optional

class AIResponse(BaseModel):
    text: str
    model: str
    usage: Optional[dict] = None
    request_id: Optional[str] = None
    processing_time: float
