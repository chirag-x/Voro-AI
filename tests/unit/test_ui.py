import pytest
from PySide6.QtWidgets import QApplication
from app.ui.overlay import OverlayWindow, UIBridge
import sys

# PySide6 requires a QApplication instance
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

def test_overlay_states(qapp):
    overlay = OverlayWindow()
    bridge = UIBridge()
    bridge.answer_received.connect(overlay.update_answer)
    bridge.privacy_status_updated.connect(overlay.update_privacy_status)
    bridge.mic_status_updated.connect(overlay.update_mic_status)
    bridge.ai_status_updated.connect(overlay.update_ai_status)
    bridge.user_input_received.connect(overlay.update_user_input)
    bridge.processing_state_updated.connect(overlay.update_processing_state)
    bridge.error_received.connect(overlay.update_error)
    bridge.clear_session.connect(overlay.clear)
    
    # Test mic update
    bridge.mic_status_updated.emit("LISTENING")
    assert overlay.current_mic == "LISTENING"
    assert "LISTENING" in overlay.status_label.text()
    
    # Test AI update
    bridge.ai_status_updated.emit("PROCESSING")
    assert overlay.current_ai == "PROCESSING"
    assert "PROCESSING" in overlay.status_label.text()
    
    # Test state update
    bridge.processing_state_updated.emit("ANALYZING")
    assert overlay.current_state == "ANALYZING"
    assert "ANALYZING" in overlay.status_label.text()
    
    # Test user text
    bridge.user_input_received.emit("hello")
    text = overlay.text_area.toPlainText()
    assert "USER" in text
    assert "hello" in text
    
    # Test answer text
    bridge.answer_received.emit("world")
    text = overlay.text_area.toPlainText()
    assert "VORO" in text
    assert "world" in text
    
    # Test clear
    bridge.clear_session.emit()
    assert overlay.text_area.toPlainText() == ""
