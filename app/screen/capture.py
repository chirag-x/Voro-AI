import time
import mss
from PIL import Image
from typing import List, Dict, Optional
from app.screen.models import ScreenFrame
from app.utils.logging import logger

class ScreenCapture:
    """Handles controlled screen capture using mss."""
    
    def __init__(self):
        self.sct = mss.mss()
        
    def list_monitors(self) -> List[Dict]:
        """Returns a list of connected monitors."""
        return self.sct.monitors

    def capture_full_screen(self, monitor_index: int = 1) -> Optional[ScreenFrame]:
        """Captures the specified monitor (1-indexed, 0 is all monitors combined)."""
        try:
            monitors = self.sct.monitors
            if monitor_index >= len(monitors):
                logger.error(f"[screen] Monitor {monitor_index} out of bounds.")
                return None
                
            monitor = monitors[monitor_index]
            sct_img = self.sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            return ScreenFrame(
                timestamp=time.time(),
                monitor=monitor_index,
                width=monitor["width"],
                height=monitor["height"],
                image=img
            )
        except Exception as e:
            logger.error(f"[screen] Capture failed: {e}")
            return None

    def capture_region(self, x: int, y: int, width: int, height: int) -> Optional[ScreenFrame]:
        """Captures a specific screen region."""
        try:
            bbox = {"top": y, "left": x, "width": width, "height": height}
            sct_img = self.sct.grab(bbox)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            return ScreenFrame(
                timestamp=time.time(),
                monitor=-1,  # Region capture doesn't map strictly to 1 monitor
                width=width,
                height=height,
                image=img
            )
        except Exception as e:
            logger.error(f"[screen] Region capture failed: {e}")
            return None
