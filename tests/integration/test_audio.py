import pytest
import time
import numpy as np
from app.audio.device import AudioDeviceManager
from app.audio.capture import AudioCaptureEngine
from app.audio.buffer import AudioBuffer
from app.utils.errors import AudioError

def test_device_discovery():
    manager = AudioDeviceManager()
    devices = manager.list_input_devices()
    assert isinstance(devices, list)
    
    # We might not have a microphone in a CI environment, 
    # but we can still check if the function ran successfully without crashing.
    default_device = manager.get_default_input_device()
    if devices:
        assert default_device is not None
        assert "name" in default_device
        assert "index" in default_device

def test_buffer_behavior():
    buffer = AudioBuffer(max_chunks=2)
    chunk1 = np.zeros(1024, dtype='float32')
    chunk2 = np.ones(1024, dtype='float32')
    chunk3 = np.full(1024, 2.0, dtype='float32')
    
    buffer.add_chunk(chunk1)
    buffer.add_chunk(chunk2)
    assert len(buffer) == 2
    
    # Adding a 3rd should drop the 1st
    buffer.add_chunk(chunk3)
    assert len(buffer) == 2
    
    chunks = buffer.get_chunks()
    assert len(chunks) == 2
    assert len(buffer) == 0
    assert np.array_equal(chunks[0], chunk2)
    assert np.array_equal(chunks[1], chunk3)

def test_capture_engine_lifecycle():
    manager = AudioDeviceManager()
    default_device = manager.get_default_input_device()
    
    if not default_device:
        pytest.skip("No default audio input device available for testing capture")
        
    engine = AudioCaptureEngine(
        device_index=default_device['index'],
        sample_rate=16000,
        channels=1,
        chunk_size=1024
    )
    
    engine.initialize()
    assert engine.stream is not None
    
    engine.start()
    assert engine.is_running()
    
    # Wait for some chunks
    time.sleep(1.0)
    
    chunks = engine.buffer.get_chunks()
    
    engine.stop()
    assert not engine.is_running()
    
    engine.shutdown()
    assert engine.stream is None
    
    # Verify we actually captured some audio data
    assert len(chunks) > 0

def test_invalid_device():
    engine = AudioCaptureEngine(
        device_index=9999, # Invalid index
        sample_rate=16000,
        channels=1,
        chunk_size=1024
    )
    with pytest.raises(AudioError):
        engine.initialize()
