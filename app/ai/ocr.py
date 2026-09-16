import logging
from PySide6.QtGui import QImage
import pytesseract
from PIL import Image

from app.core.config import load_config

# Fix for Windows Tesseract installation path
pytesseract.pytesseract.tesseract_cmd = load_config().tesseract_path

logger = logging.getLogger(__name__)

def extract_text_from_pixmap(pixmap) -> str:
    try:
        # Convert QPixmap to QImage
        image = pixmap.toImage()
        image = image.convertToFormat(QImage.Format.Format_RGB32)
        
        width = image.width()
        height = image.height()
        
        # Get raw bytes from QImage
        ptr = image.bits()
        arr = ptr.tobytes() if hasattr(ptr, 'tobytes') else bytes(ptr)
        
        # Load into PIL
        pil_img = Image.frombytes("RGBA", (width, height), arr, "raw", "BGRA")
        pil_img = pil_img.convert("RGB")
        
        text = pytesseract.image_to_string(pil_img)
        return text.strip()
    except Exception as e:
        logger.error(f"[ocr] Failed to extract text: {e}")
        return ""
