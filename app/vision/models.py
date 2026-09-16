from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from enum import Enum

class ContentType(str, Enum):
    UNKNOWN = "UNKNOWN"
    TEXT = "TEXT"
    CODE = "CODE"
    TERMINAL = "TERMINAL"
    BROWSER = "BROWSER"
    DOCUMENT = "DOCUMENT"
    QUESTION = "QUESTION"

class OCRRegion(BaseModel):
    text: str
    confidence: float
    bounding_box: List[int]  # [x_min, y_min, x_max, y_max]

class OCRResult(BaseModel):
    text: str
    confidence: float
    regions: List[OCRRegion] = Field(default_factory=list)
    timestamp: float
    base64_image: Optional[str] = None

class ScreenAnalysis(BaseModel):
    content_type: ContentType
    confidence: float
    text: str
    metadata: Dict[str, str] = Field(default_factory=dict)
