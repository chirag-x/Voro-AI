import re
from app.coding.models import CodingContext
from app.vision.models import ScreenAnalysis, ContentType

class CodingIntelligence:
    def __init__(self):
        self.language_hints = {
            "Python": ["def ", "import ", "print(", "elif "],
            "JavaScript": ["function ", "const ", "let ", "console.log", "=>"],
            "Java": ["public class", "System.out.print", "String[] args"],
            "C++": ["#include", "std::", "cout", "int main("]
        }

    def detect_language(self, text: str) -> str:
        best_lang = "UNKNOWN"
        max_score = 0
        
        for lang, hints in self.language_hints.items():
            score = sum(1 for hint in hints if hint in text)
            if score > max_score:
                max_score = score
                best_lang = lang
                
        return best_lang

    def extract_context(self, analysis: ScreenAnalysis) -> CodingContext:
        if analysis.content_type != ContentType.CODE:
            return CodingContext()
            
        text = analysis.text
        language = self.detect_language(text)
        
        # Heuristics for errors
        visible_error = None
        lower_text = text.lower()
        if "traceback (most recent call last):" in lower_text or "error:" in lower_text or "exception" in lower_text:
            # Try to grab the error section
            lines = text.split('\n')
            error_lines = [l for l in lines if "error" in l.lower() or "exception" in l.lower() or "traceback" in l.lower()]
            if error_lines:
                visible_error = "\n".join(error_lines)
                
        # Basic parsing
        return CodingContext(
            language=language,
            code=text,  # For now, treat the whole block as code if it's marked CODE
            visible_error=visible_error,
            confidence=analysis.confidence
        )
