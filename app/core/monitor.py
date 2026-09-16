import time
import threading
import numpy as np
import mss
from PIL import Image
from app.utils.logging import logger

class ScreenMonitor:
    def __init__(self, application, interval: float = 3.0, threshold: float = 200.0):
        self.application = application
        self.interval = interval
        self.threshold = threshold
        self.running = False
        self.thread = None
        
        self.last_hash = None
        
    def start(self):
        if not getattr(self.application.config, 'enable_auto_monitor', False):
            return
            
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.thread.start()
            logger.info("[monitor] Auto-Monitor started.")
            
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            
    def _compute_hash(self, img_pil: Image.Image) -> np.ndarray:
        # Resize to 32x32 grayscale for extremely fast structural comparison
        img_small = img_pil.resize((32, 32)).convert('L')
        return np.array(img_small, dtype=np.float32)

    def _monitor_loop(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1] # Primary monitor
            while self.running:
                try:
                    sct_img = sct.grab(monitor)
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    
                    current_hash = self._compute_hash(img)
                    
                    if self.last_hash is not None:
                        # Compute Mean Squared Error (MSE)
                        mse = np.mean((self.last_hash - current_hash) ** 2)
                        
                        if mse > self.threshold:
                            logger.info(f"[monitor] Significant screen change detected (MSE: {mse:.1f})")
                            # It changed! Wait a moment to let the user finish typing/pasting
                            time.sleep(1.0)
                            
                            # Grab fresh image after stabilization
                            sct_img = sct.grab(monitor)
                            img_stable = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                            self.last_hash = self._compute_hash(img_stable)
                            
                            # Inject into application queue
                            if hasattr(self.application, 'on_snip_callback'):
                                # We can reuse the snip callback logic to process the screen
                                logger.info("[monitor] Triggering silent background analysis")
                                self.application.on_snip_callback(img_stable, auto=True)
                                
                    else:
                        self.last_hash = current_hash
                        
                except Exception as e:
                    logger.error(f"[monitor] Error in auto-monitor loop: {e}")
                    
                time.sleep(self.interval)
