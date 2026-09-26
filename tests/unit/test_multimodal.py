import pytest
from app.multimodal.context import MultiModalContextEngine
from app.context.manager import ContextManager
from app.vision.models import OCRResult, ScreenAnalysis, ContentType
from app.coding.models import CodingContext
from app.session.models import ConversationTurn, Role

def test_multimodal_context_builder(tmp_path):
    ctx_mgr = ContextManager(storage_path=str(tmp_path / "c.json"))
    mm_engine = MultiModalContextEngine(ctx_mgr)
    
    ocr = OCRResult(text="def add(): pass", confidence=0.9, timestamp=10.0)
    analysis = ScreenAnalysis(content_type=ContentType.CODE, confidence=0.9, text="def add(): pass")
    coding = CodingContext(language="Python", code="def add(): pass")
    
    mm_engine.update_screen_context(ocr, analysis, coding)
    
    # 1. Ask for screen context implicitly
    mm_ctx = mm_engine.build_context("what is wrong with this code?", 1)
    assert mm_ctx.ocr_text is not None
    assert mm_ctx.coding_context is not None
    assert mm_ctx.coding_context.language == "Python"
    
    # 2. Doesn't need screen context, but it's fresh (not testing freshness here easily because of time.time() mocking)
    # But let's test that the prompt builder formats it correctly
    prompt_addition = mm_engine.build_system_prompt_addition(mm_ctx)
    assert "VISIBLE SCREEN CONTENT" in prompt_addition
    assert "Python" in prompt_addition
    assert "def add(): pass" in prompt_addition
