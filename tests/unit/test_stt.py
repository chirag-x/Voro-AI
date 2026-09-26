import pytest
import numpy as np
from app.speech.stt import SpeechToText
from app.speech.models import TranscriptResult

class MockSegment:
    def __init__(self, text):
        self.text = text

class MockInfo:
    def __init__(self, language, language_probability, duration):
        self.language = language
        self.language_probability = language_probability
        self.duration = duration

class MockWhisperModel:
    def __init__(self, *args, **kwargs):
        pass
        
    def transcribe(self, audio, **kwargs):
        segments = [MockSegment(" Hello"), MockSegment(" world.")]
        info = MockInfo("en", 0.99, 2.5)
        return segments, info

def test_stt_transcribe(monkeypatch):
    monkeypatch.setattr("app.speech.stt.WhisperModel", MockWhisperModel)
    
    stt = SpeechToText(model_size="tiny.en")
    stt.initialize()
    
    audio_segment = np.zeros(16000, dtype=np.float32)
    result = stt.transcribe(audio_segment)
    
    assert isinstance(result, TranscriptResult)
    assert result.text == "Hello  world."
    assert result.language == "en"
    assert result.confidence == 0.99
    assert result.duration == 2.5
    assert result.processing_time > 0

def test_stt_not_initialized():
    stt = SpeechToText()
    audio_segment = np.zeros(16000, dtype=np.float32)
    with pytest.raises(RuntimeError):
        stt.transcribe(audio_segment)
