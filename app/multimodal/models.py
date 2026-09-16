from pydantic import BaseModel, Field
from typing import Optional
from app.coding.models import CodingContext
from app.vision.models import ScreenAnalysis, OCRResult

class MultiModalContext(BaseModel):
    current_user_text: str = ""
    session_turns: int = 0
    interview_context_active: bool = False
    
    ocr_text: Optional[str] = None
    base64_image: Optional[str] = None
    screen_analysis: Optional[ScreenAnalysis] = None
    coding_context: Optional[CodingContext] = None
    
    screen_timestamp: float = 0.0
    
    def is_screen_fresh(self, current_time: float, max_age: float = 60.0) -> bool:
        if not self.screen_timestamp:
            return False
        return (current_time - self.screen_timestamp) <= max_age
