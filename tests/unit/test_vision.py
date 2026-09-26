import pytest
from app.vision.models import OCRResult, OCRRegion, ContentType
from app.vision.analyzer import ScreenAnalyzer

def test_screen_analyzer_empty():
    analyzer = ScreenAnalyzer()
    res = analyzer.analyze(OCRResult(text="", confidence=0.0, timestamp=0.0))
    assert res.content_type == ContentType.UNKNOWN

def test_screen_analyzer_question():
    analyzer = ScreenAnalyzer()
    res = analyzer.analyze(OCRResult(
        text="What is polymorphism?", 
        confidence=0.9, 
        timestamp=0.0
    ))
    assert res.content_type == ContentType.QUESTION

def test_screen_analyzer_code():
    analyzer = ScreenAnalyzer()
    code_text = "def add(a, b):\n    return a + b\n"
    res = analyzer.analyze(OCRResult(
        text=code_text, 
        confidence=0.9, 
        timestamp=0.0
    ))
    assert res.content_type == ContentType.CODE
    assert "code_score" in res.metadata
