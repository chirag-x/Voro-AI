import pytest
import numpy as np
from app.audio.vad import VadEngine, VadEvent

def test_vad_silence():
    vad = VadEngine(sample_rate=16000, aggressiveness=3)
    # Generate silence
    chunk = np.zeros(16000, dtype=np.float32)
    events = vad.process_chunk(chunk)
    assert len(events) == 0
    assert not vad.triggered

def test_vad_speech():
    vad = VadEngine(sample_rate=16000, aggressiveness=3)
    # Generate high amplitude voro which webrtcvad often detects as speech
    np.random.seed(42)
    chunk = np.random.uniform(-0.5, 0.5, 16000).astype(np.float32)
    events = vad.process_chunk(chunk)
    
    assert vad.triggered
    assert any(e == VadEvent.SPEECH_STARTED for e, _ in events)
    
    # Generate silence to trigger SPEECH_ENDED
    silence = np.zeros(16000, dtype=np.float32)
    events = vad.process_chunk(silence)
    
    assert not vad.triggered
    assert any(e == VadEvent.SPEECH_ENDED for e, _ in events)
    
    # Check that we received a segment
    end_event = [ev for ev in events if ev[0] == VadEvent.SPEECH_ENDED][0]
    segment = end_event[1]
    assert segment is not None
    assert len(segment) > 0

def test_vad_reset():
    vad = VadEngine(sample_rate=16000, aggressiveness=3)
    np.random.seed(42)
    chunk = np.random.uniform(-0.5, 0.5, 16000).astype(np.float32)
    vad.process_chunk(chunk)
    assert vad.triggered
    
    vad.reset()
    assert not vad.triggered
    assert len(vad._audio_buffer) == 0
    assert len(vad.current_speech_segment) == 0
