import pytest
import os
from app.core.state import ApplicationState
from app.core.config import load_config, VoroConfig
from app.core.application import VoroApplication
from app.utils.errors import ConfigError

def test_config_loading(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test_key")
    config = load_config()
    assert config.openrouter_api_key == "test_key"
    assert config.audio_sample_rate == 16000

def test_app_initial_state():
    app = VoroApplication()
    assert app.state == ApplicationState.STARTING

def test_app_initialize(monkeypatch):
    # Mock audio to avoid actual hardware initialization in unit tests
    def mock_init(self):
        pass
    def mock_start(self):
        pass
    monkeypatch.setattr("app.audio.capture.AudioCaptureEngine.initialize", mock_init)
    monkeypatch.setattr("app.audio.capture.AudioCaptureEngine.start", mock_start)
    
    app = VoroApplication()
    app.initialize()
    assert app.state == ApplicationState.READY
    assert app.config is not None

def test_app_start_shutdown(monkeypatch):
    def mock_init(self):
        pass
    def mock_start(self):
        pass
    monkeypatch.setattr("app.audio.capture.AudioCaptureEngine.initialize", mock_init)
    monkeypatch.setattr("app.audio.capture.AudioCaptureEngine.start", mock_start)

    app = VoroApplication()
    app.initialize()
    app.start()
    assert app.state == ApplicationState.RUNNING
    
    app.shutdown()
    assert app.state == ApplicationState.STOPPED

def test_repeated_shutdown(monkeypatch):
    def mock_init(self):
        pass
    def mock_start(self):
        pass
    monkeypatch.setattr("app.audio.capture.AudioCaptureEngine.initialize", mock_init)
    monkeypatch.setattr("app.audio.capture.AudioCaptureEngine.start", mock_start)

    app = VoroApplication()
    app.initialize()
    app.shutdown()
    assert app.state == ApplicationState.STOPPED
    
    # Second shutdown should not crash
    app.shutdown()
    assert app.state == ApplicationState.STOPPED

def test_startup_failure(monkeypatch):
    def mock_load_config():
        raise ConfigError("Simulated failure")
    
    monkeypatch.setattr("app.core.application.load_config", mock_load_config)
    
    app = VoroApplication()
    with pytest.raises(ConfigError):
        app.initialize()
    
    assert app.state == ApplicationState.FAILED
