import time
from app.multimodal.models import MultiModalContext
from app.vision.models import OCRResult, ScreenAnalysis, ContentType
from app.coding.models import CodingContext
from app.context.manager import ContextManager
from app.utils.logging import logger

class MultiModalContextEngine:
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
        
        # Latest screen state
        self.latest_ocr: OCRResult = None
        self.latest_analysis: ScreenAnalysis = None
        self.latest_coding: CodingContext = None
        
    def update_screen_context(self, ocr: OCRResult, analysis: ScreenAnalysis, coding: CodingContext):
        self.latest_ocr = ocr
        self.latest_analysis = analysis
        self.latest_coding = coding
        logger.info("[multimodal] Screen context updated")
        
    def clear_context(self):
        """Clears all ephemeral multimodal context."""
        self.latest_ocr = None
        self.latest_analysis = None
        self.latest_coding = None
        logger.info("[multimodal] Screen context cleared")

    def build_context(self, user_text: str, session_turns: int) -> MultiModalContext:
        ctx = MultiModalContext(
            current_user_text=user_text,
            session_turns=session_turns,
            interview_context_active=bool(self.context_manager.current_context.interview.role)
        )
        
        if self.latest_ocr:
            ctx.screen_timestamp = self.latest_ocr.timestamp
            
        current_time = time.time()
        
        # Decide if screen is relevant
        text_lower = user_text.lower()
        needs_screen = any(w in text_lower for w in ["this", "here", "on screen", "look at", "code"])
        
        # If it's a very fresh screen capture, we can assume it might be relevant
        is_fresh = ctx.is_screen_fresh(current_time, max_age=30.0)
        
        if needs_screen or is_fresh:
            if self.latest_ocr:
                # Bounded OCR text
                ctx.ocr_text = self.latest_ocr.text[:2000] if self.latest_ocr.text else ""
                ctx.base64_image = self.latest_ocr.base64_image
            ctx.screen_analysis = self.latest_analysis
            ctx.coding_context = self.latest_coding
            
        return ctx

    def build_system_prompt_addition(self, mm_ctx: MultiModalContext) -> str:
        parts = []
        if mm_ctx.ocr_text:
            parts.append("--- VISIBLE SCREEN CONTENT ---")
            parts.append(f"OCR Confidence: {self.latest_ocr.confidence:.2f}")
            if mm_ctx.screen_analysis:
                parts.append(f"Detected Type: {mm_ctx.screen_analysis.content_type.value}")
            
            if mm_ctx.coding_context and mm_ctx.coding_context.language != "UNKNOWN":
                parts.append(f"Detected Language: {mm_ctx.coding_context.language}")
                if mm_ctx.coding_context.code:
                    parts.append(f"Extracted Code:\n```\n{mm_ctx.coding_context.code}\n```")
                if mm_ctx.coding_context.visible_error:
                    parts.append(f"Visible Error:\n{mm_ctx.coding_context.visible_error}")
                parts.append(f"Other Visible Screen Text:\n{mm_ctx.ocr_text}")
            else:
                parts.append(f"Visible Text:\n{mm_ctx.ocr_text}")
            
        if parts:
            return "\n".join(parts)
        return ""
