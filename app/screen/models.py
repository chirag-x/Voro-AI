from pydantic import BaseModel
from typing import Optional
from PIL.Image import Image

class ScreenFrame(BaseModel):
    timestamp: float
    monitor: int
    width: int
    height: int
    image: Image

    class Config:
        arbitrary_types_allowed = True
