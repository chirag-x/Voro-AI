import platform
from app.platform.windows.privacy import check_privacy_capabilities

def test_windows_capabilities(monkeypatch):
    # Test on a simulated Windows environment
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(platform, "release", lambda: "10")
    
    caps = check_privacy_capabilities()
    assert "Display privacy capability" in caps
    assert caps["Display privacy capability"] == "AVAILABLE"
    assert caps["Capture exclusion support"] == "AVAILABLE"

def test_non_windows_capabilities(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    
    caps = check_privacy_capabilities()
    assert caps["Display privacy capability"] == "UNAVAILABLE"
    assert caps["Capture exclusion support"] == "UNAVAILABLE"
