import pytest
from app.coding.detector import CodingIntelligence
from app.vision.models import ScreenAnalysis, ContentType
from app.coding.models import CodingContext

def test_language_detection():
    detector = CodingIntelligence()
    
    lang = detector.detect_language("def add(a, b):\n    return a + b\n")
    assert lang == "Python"
    
    lang = detector.detect_language("const obj = {};\nconsole.log(obj);")
    assert lang == "JavaScript"
    
    lang = detector.detect_language("public class Main {\n    public static void main(String[] args) {}")
    assert lang == "Java"
    
def test_coding_context_extraction():
    detector = CodingIntelligence()
    
    analysis = ScreenAnalysis(
        content_type=ContentType.CODE,
        confidence=0.9,
        text="def foo():\n    pass\n\nTraceback (most recent call last):\nNameError: name 'bar' is not defined"
    )
    
    ctx = detector.extract_context(analysis)
    assert ctx.language == "Python"
    assert "Traceback" in ctx.visible_error
    assert ctx.confidence == 0.9

def test_coding_context_ignore_non_code():
    detector = CodingIntelligence()
    
    analysis = ScreenAnalysis(
        content_type=ContentType.TEXT,
        confidence=0.9,
        text="Just some text"
    )
    
    ctx = detector.extract_context(analysis)
    assert ctx.language == "UNKNOWN"
    assert ctx.code is None
