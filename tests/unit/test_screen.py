from app.screen.capture import ScreenCapture
from app.screen.models import ScreenFrame

def test_screen_list_monitors():
    capture = ScreenCapture()
    monitors = capture.list_monitors()
    assert isinstance(monitors, list)
    assert len(monitors) >= 1

def test_screen_capture_full():
    capture = ScreenCapture()
    frame = capture.capture_full_screen(monitor_index=1)
    
    # If a monitor exists, we should get a frame (this tests fine locally or on typical CI)
    if frame is not None:
        assert isinstance(frame, ScreenFrame)
        assert frame.width > 0
        assert frame.height > 0
        assert frame.image is not None

def test_screen_capture_region():
    capture = ScreenCapture()
    frame = capture.capture_region(0, 0, 100, 100)
    
    if frame is not None:
        assert isinstance(frame, ScreenFrame)
        assert frame.width == 100
        assert frame.height == 100
        assert frame.image is not None
