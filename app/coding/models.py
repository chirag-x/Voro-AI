from pydantic import BaseModel
from typing import Optional

class CodingContext(BaseModel):
    language: str = "UNKNOWN"
    problem_statement: Optional[str] = None
    code: Optional[str] = None
    visible_error: Optional[str] = None
    visible_output: Optional[str] = None
    confidence: float = 0.0
