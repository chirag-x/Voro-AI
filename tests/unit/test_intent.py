from app.intent.detector import IntentDetector
from app.intent.models import Intent, IntentSource

def test_intent_question():
    detector = IntentDetector()
    
    res = detector.detect("What is recursion")
    assert res.intent == Intent.QUESTION
    
    res = detector.detect("Explain binary search")
    assert res.intent == Intent.QUESTION
    
    res = detector.detect("how does it work?")
    assert res.intent == Intent.QUESTION

def test_intent_conversation():
    detector = IntentDetector()
    
    res = detector.detect("hello")
    assert res.intent == Intent.CONVERSATION
    
    res = detector.detect("Thanks!")
    assert res.intent == Intent.CONVERSATION

def test_intent_command():
    detector = IntentDetector()
    
    res = detector.detect("reset session")
    assert res.intent == Intent.COMMAND
    
    res = detector.detect("clear conversation  ")
    assert res.intent == Intent.COMMAND

def test_intent_unknown():
    detector = IntentDetector()
    
    res = detector.detect("this is something unclear")
    assert res.intent == Intent.UNKNOWN
