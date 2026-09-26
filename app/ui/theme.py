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
