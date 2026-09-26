import time
import mss
from PIL import Image
from typing import List, Dict, Optional
from app.screen.models import ScreenFrame
from app.utils.logging import logger
import ctypes
from ctypes import wintypes

class ScreenCapture:
    """Handles controlled screen capture using mss."""
    
    def __init__(self):
        self.sct = mss.mss()
        
    def list_monitors(self) -> List[Dict]:
        """Returns a list of connected monitors."""
        return self.sct.monitors
        
    def list_windows(self) -> List[str]:
        """Returns a list of visible window titles."""
        titles = []
        EnumWindows = ctypes.windll.user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        GetWindowText = ctypes.windll.user32.GetWindowTextW
        GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
        IsWindowVisible = ctypes.windll.user32.IsWindowVisible
        
        def foreach_window(hwnd, lParam):
            if IsWindowVisible(hwnd):
                length = GetWindowTextLength(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    GetWindowText(hwnd, buff, length + 1)
                    titles.append(buff.value)
            return True
            
        EnumWindows(EnumWindowsProc(foreach_window), 0)
        return sorted(list(set(titles)))

    def capture_full_screen(self, monitor_index: int = 1) -> Optional[ScreenFrame]:
        """Captures based on config (monitor or window)."""
        from app.core.config import load_config
        config = load_config()
        
        mode = getattr(config, 'ui_capture_mode', 'monitor')
        target = getattr(config, 'ui_capture_target', '1')
        
        try:
            if mode == 'window':
                hwnd = ctypes.windll.user32.FindWindowW(None, target)
                if hwnd:
                    rect = wintypes.RECT()
                    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    bbox = {"left": rect.left, "top": rect.top, "width": max(1, rect.right - rect.left), "height": max(1, rect.bottom - rect.top)}
                    sct_img = self.sct.grab(bbox)
                    monitor_id = 0
                else:
                    logger.error(f"[screen] Window '{target}' not found. Falling back to monitor 1.")
                    sct_img = self.sct.grab(self.sct.monitors[1])
                    monitor_id = 1
            else:
                idx = int(target)
                monitors = self.sct.monitors
                if idx >= len(monitors):
                    idx = 1
                sct_img = self.sct.grab(monitors[idx])
                monitor_id = idx
                
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            return ScreenFrame(
                timestamp=time.time(),
                monitor=monitor_id,
                width=sct_img.width,
                height=sct_img.height,
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
                monitor=-1,
                width=width,
                height=height,
                image=img
            )
        except Exception as e:
            logger.error(f"[screen] Region capture failed: {e}")
            return None
