import re
from app.vision.models import OCRResult, ScreenAnalysis, ContentType

class ScreenAnalyzer:
    def __init__(self):
        self.code_keywords = {
            "def ", "class ", "import ", "from ", "function ", 
            "const ", "let ", "var ", "public ", "private ", 
            "if ", "else", "for ", "while ", "return "
        }
        self.code_symbols = {"{", "}", "()", ";", "=>", "::", "[]"}
        
        self.question_words = ["what is", "explain", "how to", "difference between", "why do we", "write a"]

    def analyze(self, ocr_result: OCRResult) -> ScreenAnalysis:
        if not ocr_result.text or ocr_result.confidence < 0.2:
            return ScreenAnalysis(
                content_type=ContentType.UNKNOWN,
                confidence=ocr_result.confidence,
                text=ocr_result.text
            )

        lower_text = ocr_result.text.lower()
        
        # 1. Question Detection
        is_question = False
        if "?" in lower_text:
            is_question = True
        elif any(q in lower_text for q in self.question_words):
            is_question = True
            
        if is_question and len(ocr_result.text.split()) < 50:
            return ScreenAnalysis(
                content_type=ContentType.QUESTION,
                confidence=ocr_result.confidence,
                text=ocr_result.text
            )
            
        # 2. Code Detection
        code_score = 0
        for kw in self.code_keywords:
            if kw in lower_text:
                code_score += 1
                
        for sym in self.code_symbols:
            if sym in ocr_result.text:
                code_score += 1
                
        if code_score >= 2:
            return ScreenAnalysis(
                content_type=ContentType.CODE,
                confidence=min(0.95, ocr_result.confidence + 0.1),
                text=ocr_result.text,
                metadata={"code_score": str(code_score)}
            )
            
        # 3. Default to text
        return ScreenAnalysis(
            content_type=ContentType.TEXT,
            confidence=ocr_result.confidence,
            text=ocr_result.text
        )
