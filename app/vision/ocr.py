import time
import numpy as np
import threading
from typing import Optional
from app.vision.models import OCRResult, OCRRegion
from app.screen.models import ScreenFrame
from app.utils.logging import logger

# Lazy load easyocr so it doesn't block startup
_reader = None
_reader_lock = threading.Lock()

def _get_reader():
    global _reader
    with _reader_lock:
        if _reader is None:
            import easyocr
            import warnings
            from app.core.config import load_config
            
            config = load_config()
            use_gpu = getattr(config, 'ocr_device', 'gpu').lower() == 'gpu'
            
            logger.info(f"Initializing EasyOCR on {'GPU' if use_gpu else 'CPU'} (this may take a moment)...")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                _reader = easyocr.Reader(['en'], gpu=use_gpu, verbose=False)
    return _reader

class OCREngine:
    def __init__(self):
        pass

    def extract_text(self, frame: ScreenFrame, skip_ocr: bool = False) -> OCRResult:
        try:
            # Encode image to base64 for Vision Models first
            import io
            import base64
            buffered = io.BytesIO()
            frame.image.save(buffered, format="PNG")
            b64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            if skip_ocr:
                # Fast path for Premium users who use vision models instead of OCR
                return OCRResult(
                    text="",
                    confidence=1.0,
                    regions=[],
                    timestamp=time.time(),
                    base64_image=b64_image
                )

            reader = _get_reader()
            
            # Convert PIL image to numpy array for easyocr
            img_np = np.array(frame.image)
            
            # Run OCR
            results = reader.readtext(img_np, paragraph=False)
            
            ocr_regions = []
            full_text_lines = []
            total_confidence = 0.0
            
            for (bbox, text, prob) in results:
                # bbox is [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
                x_min, x_max = min(x_coords), max(x_coords)
                y_min, y_max = min(y_coords), max(y_coords)
                
                clean_text = str(text).strip()
                if clean_text:
                    ocr_regions.append(OCRRegion(
                        text=clean_text,
                        confidence=prob,
                        bounding_box=[int(x_min), int(y_min), int(x_max), int(y_max)]
                    ))
                    full_text_lines.append(clean_text)
                    total_confidence += prob
            
            avg_confidence = (total_confidence / len(ocr_regions)) if ocr_regions else 0.0
            
            return OCRResult(
                text="\n".join(full_text_lines),
                confidence=avg_confidence,
                regions=ocr_regions,
                timestamp=time.time(),
                base64_image=b64_image
            )
            
        except Exception as e:
            logger.error(f"[ocr] Extraction failed: {e}")
            return OCRResult(text="", confidence=0.0, timestamp=time.time())
