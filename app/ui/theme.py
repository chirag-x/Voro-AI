"""
theme.py - Detects the Windows light/dark app theme via the registry
and returns appropriate background and base text colors.
"""

def is_windows_dark_mode() -> bool:
    """Returns True if Windows is set to dark app theme."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0  # 0 = dark, 1 = light
    except Exception:
        return False  # Default to light if registry not readable


def get_theme_colors(theme_mode: str = "system") -> dict:
    """
    Returns bg and base_text colors matching the requested or current Windows theme.
    - bg:        window background color
    - base_text: default text/label color (contrasts with bg)
    """
    is_dark = False
    if theme_mode.lower() == "dark":
        is_dark = True
    elif theme_mode.lower() == "light":
        is_dark = False
    else:
        is_dark = is_windows_dark_mode()
        
    if is_dark:
        return {
            "bg": "#1E1E1E",
            "base_text": "#E0E0E0",
            "border": "#444444",
        }
    else:
        return {
            "bg": "#F5F5F5",
            "base_text": "#1A1A1A",
            "border": "#BBBBBB",
        }


def apply_native_titlebar_theme(hwnd, is_dark: bool):
    """Applies Windows immersive dark mode (or light mode) to the window's title bar."""
    if not hwnd:
        return
    try:
        import sys
        if sys.platform == "win32":
            import ctypes
            from ctypes import c_int, byref, sizeof
            val = c_int(1 if is_dark else 0)
            res = ctypes.windll.dwmapi.DwmSetWindowAttribute(int(hwnd), 20, byref(val), sizeof(val))
            if res != 0:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(int(hwnd), 19, byref(val), sizeof(val))
    except Exception:
        pass


def style_message_box(box, theme_mode: str = "system", parent=None):
    """
    Applies consistent Light/Dark styling to a QMessageBox, ensuring crisp typography,
    matching dialog background, branded buttons, and light/dark title bar.
    """
    colors = get_theme_colors(theme_mode)
    is_dark = colors.get("bg", "#1E1E1E") == "#1E1E1E"

    bg_col = "#1E1E1E" if is_dark else "#FFFFFF"
    text_col = "#E2E8F0" if is_dark else "#1E293B"
    btn_bg = "#0078D7" if is_dark else "#0055A4"
    btn_hover = "#0066CC" if is_dark else "#004080"
    btn_border = "#3B82F6" if is_dark else "#0055A4"

    box.setStyleSheet(f"""
        QMessageBox {{
            background-color: {bg_col};
        }}
        QLabel {{
            color: {text_col};
            font-size: 13px;
            background-color: transparent;
        }}
        QPushButton {{
            background-color: {btn_bg};
            color: #FFFFFF;
            border: 1px solid {btn_border};
            border-radius: 6px;
            padding: 7px 24px;
            font-weight: bold;
            font-size: 13px;
            min-width: 75px;
        }}
        QPushButton:hover {{
            background-color: {btn_hover};
        }}
    """)

    # App icon
    try:
        import os
        from PySide6.QtGui import QIcon
        for icon_name in ["logo.png", "logo.ico", "norvi_logo.png"]:
            if os.path.exists(icon_name):
                box.setWindowIcon(QIcon(icon_name))
                break
    except Exception:
        pass

    # Windows native title bar theme
    try:
        box.winId()
        apply_native_titlebar_theme(int(box.winId()), is_dark)
    except Exception:
        pass

    # Stealth mode inheritance if parent has stealth active
    if parent and getattr(parent, "_stealth_active", False) and hasattr(parent, "_apply_privacy_flag"):
        try:
            parent._apply_privacy_flag(stealth=True, target_hwnd=int(box.winId()))
        except Exception:
            pass

    return box
