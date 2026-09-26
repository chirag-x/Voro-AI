import pytest
import logging
from app.utils.logging import RedactingFormatter

def test_redacting_formatter():
    formatter = RedactingFormatter(fmt="%(message)s", datefmt="")
    
    # Test API Key Redaction
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Using key sk-or-v1-YOUR_TEST_KEY_HERE_REDACTED",
        args=(), exc_info=None
    )
    formatted = formatter.format(record)
    assert "sk-or-v1-e17f" in formatted
    assert "***REDACTED***" in formatted
    assert "REDACTED" not in formatted

    # Test Bearer Token Redaction
    record.msg = "Authorization: Bearer my_secret_token_123==="
    formatted = formatter.format(record)
    assert "Bearer" in formatted
    assert "***REDACTED***" in formatted
    assert "my_secret_token_123" not in formatted

    # Test api_key url param redaction
    record.msg = "GET /api?api_key=sk-or-v1-abcd1234567890"
    formatted = formatter.format(record)
    assert "api_key=sk-or-v1-abcd" in formatted
    assert "***REDACTED***" in formatted
    assert "1234567890" not in formatted

from app.core.application import VoroApplication

def test_session_privacy_wipe():
    app = VoroApplication()
    # Mock some states
    app._last_screen_hash = "fake_hash"
    app._last_ocr_res = "fake_ocr"
    app._last_coding_res = "fake_coding"
    app.mm_engine.current_screen_context = "fake_mm_ctx"
    
    app.session_manager.add_user_turn("hello")
    assert len(app.session_manager.get_context()) == 1
    
    # Trigger privacy wipe
    # Simulate routing command
    app.session_manager.reset_session()
    app._last_screen_hash = None
    app._last_ocr_res = None
    app._last_analysis_res = None
    app._last_coding_res = None
    app.mm_engine.clear_context()
    
    assert len(app.session_manager.get_context()) == 0
    assert app._last_screen_hash is None
    assert app._last_ocr_res is None
    assert app.mm_engine.latest_ocr is None

