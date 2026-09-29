import time
import threading
from typing import Optional
from app.vision.models import OCRResult, OCRRegion
from app.screen.models import ScreenFrame
from app.utils.logging import logger
import os

_tesseract_configured = False
_tesseract_lock = threading.Lock()

def _configure_tesseract():
    global _tesseract_configured
    with _tesseract_lock:
        if not _tesseract_configured:
            try:
                import pytesseract
                from app.core.config import load_config
                config = load_config()
                
                env_tess = os.environ.get("TESSERACT_CMD_PATH", "")
                if env_tess and os.path.exists(env_tess):
                    pytesseract.pytesseract.tesseract_cmd = env_tess
                else:
                    pytesseract.pytesseract.tesseract_cmd = config.tesseract_path
                    
                _tesseract_configured = True
                logger.info(f"Initialized PyTesseract on CPU (path: {pytesseract.pytesseract.tesseract_cmd})")
            except Exception as e:
                logger.error(f"Failed to configure Tesseract: {e}")

class OCREngine:
    def __init__(self):
        _configure_tesseract()

    def extract_text(self, frame: ScreenFrame, skip_ocr: bool = False) -> OCRResult:
        try:
            # Encode image to base64 for Vision Models first
            import io
            import base64
            buffered = io.BytesIO()
            frame.image.save(buffered, format="PNG")
            b64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            if skip_ocr:
                # Fast path for users who use vision models entirely without OCR
                return OCRResult(
                    text="",
                    confidence=1.0,
                    regions=[],
                    timestamp=time.time(),
                    base64_image=b64_image
                )

            import pytesseract
            
            # Check if tesseract actually exists
            if not os.path.exists(pytesseract.pytesseract.tesseract_cmd):
                logger.warning(f"Tesseract not found at {pytesseract.pytesseract.tesseract_cmd}. Skipping OCR.")
                return OCRResult(
                    text="",
                    confidence=0.0,
                    regions=[],
                    timestamp=time.time(),
                    base64_image=b64_image
                )

            # Run Tesseract OCR on the PIL Image directly
            # output_type=Output.DICT gives us bounding boxes and confidences
            from pytesseract import Output
            data = pytesseract.image_to_data(frame.image, output_type=Output.DICT)
            
            ocr_regions = []
            full_text_lines = []
            total_confidence = 0.0
            word_count = 0
            
            current_line = []
            last_line_num = -1
            
            for i in range(len(data['text'])):
                text = str(data['text'][i]).strip()
                if text:
                    conf = float(data['conf'][i]) / 100.0  # Tesseract returns 0-100
                    x = data['left'][i]
                    y = data['top'][i]
                    w = data['width'][i]
                    h = data['height'][i]
                    line_num = data['line_num'][i]
                    
                    if line_num != last_line_num and current_line:
                        full_text_lines.append(" ".join(current_line))
                        current_line = []
                        
                    current_line.append(text)
                    last_line_num = line_num
                    
                    ocr_regions.append(OCRRegion(
                        text=text,
                        confidence=conf,
                        bounding_box=[x, y, x + w, y + h]
                    ))
                    total_confidence += conf
                    word_count += 1
            
            if current_line:
                full_text_lines.append(" ".join(current_line))
                
            avg_confidence = (total_confidence / word_count) if word_count > 0 else 0.0
            
            return OCRResult(
                text="\n".join(full_text_lines),
                confidence=avg_confidence,
                regions=ocr_regions,
                timestamp=time.time(),
                base64_image=b64_image
            )
            
        except ImportError:
            logger.error("[ocr] pytesseract module not installed")
            return OCRResult(text="", confidence=0.0, timestamp=time.time())
        except Exception as e:
            logger.error(f"[ocr] Extraction failed: {e}")
            return OCRResult(text="", confidence=0.0, timestamp=time.time())
