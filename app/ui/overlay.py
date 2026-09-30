from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl
import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton, QSystemTrayIcon, QMenu, QApplication, QSlider
from PySide6.QtCore import Qt, QObject, Signal, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtGui import QKeySequence, QShortcut

from app.ui.settings import SettingsDialog

class UIBridge(QObject):
    """
    Bridge to safely pass signals from background threads to the main UI thread.
    """
    answer_received = Signal(str)
    answer_chunk_received = Signal(str, bool, bool)
    privacy_status_updated = Signal(str)
    mic_status_updated = Signal(str)
    ai_status_updated = Signal(str)
    user_input_received = Signal(str)
    processing_state_updated = Signal(str)
    error_received = Signal(str)
    clear_session = Signal()
    quit_application = Signal()
    activation_switched = Signal(str)
    config_updated = Signal()
    tts_audio_ready = Signal(str)
    tts_stop = Signal()

    model_switched = Signal(str)
    profile_updated = Signal()
    toggle_visibility = Signal()
    trigger_snip = Signal()
    toggle_taskbar = Signal()
    toggle_tray = Signal()
    toggle_stealth = Signal()

class OverlayWindow(QWidget):
    """
    Private overlay UI for displaying answers and transcription.
    Runs in the main Qt thread.
    """
    user_mic_toggled = Signal()
    sys_mic_toggled = Signal()
    tts_toggled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Voro")
        
        from app.core.config import load_config
        from app.ui.theme import get_theme_colors
        self.config = load_config()
        self.theme = get_theme_colors(self.config.ui_theme_mode)
        self._env_path = os.path.join(os.getcwd(), ".env")
        
        # --- Feature 2: Always-on-top state ---
        self._always_on_top = self.config.ui_always_on_top
        # Must be frameless for WA_TranslucentBackground to work on Windows
        flags = Qt.Window | Qt.FramelessWindowHint
        if self._always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        
        icon_path = os.path.join(os.getcwd(), "logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # --- Feature 3: Window geometry memory ---
        if self.config.ui_remember_position and self.config.ui_win_x != -1:
            self.setGeometry(
                self.config.ui_win_x,
                self.config.ui_win_y,
                self.config.ui_win_w,
                self.config.ui_win_h
            )
        else:
            self.resize(self.config.ui_win_w, self.config.ui_win_h)
        
        # Enable true alpha-channel support for the frameless window
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Apply Master Opacity
        self.setWindowOpacity(self.config.ui_opacity / 100.0)
        
        # Apply theme with independent Background and Text base opacities
        is_dark_mode = self.theme.get('bg', '#1E1E1E') == '#1E1E1E'
        btn_panel_bg  = "#2A2A2A" if is_dark_mode else "#E8E8E8"
        border_col    = self.theme.get('border', '#444')
        text_col      = self.theme['base_text']
        bg_col_main   = self.theme['bg']
        accent        = "#0055A4"
        
        # Helper to convert hex to rgba
        def hex_to_rgba(hex_color, alpha_pct):
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 6:
                r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                return f"rgba({r}, {g}, {b}, {alpha_pct / 100.0})"
            return hex_color

        base_bg_opacity = getattr(self.config, 'ui_bg_opacity', 100)
        base_text_opacity = getattr(self.config, 'ui_text_opacity', 100)

        bg_rgba = hex_to_rgba(bg_col_main, base_bg_opacity)
        text_rgba = hex_to_rgba(text_col, base_text_opacity)
        
        self.setStyleSheet(
            f"QWidget {{ font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; color: {text_rgba}; }}"
            f"OverlayWindow {{ background-color: {bg_rgba}; border-radius: 12px; border: 1px solid {border_col}; }}"
            f"QLabel {{ color: {text_rgba}; }}"
            f"QPushButton#settings_btn {{ background-color: {btn_panel_bg}; color: {text_rgba}; border: 1px solid {border_col}; border-radius: 6px; padding: 4px 10px; font-weight: bold; }}"
            f"QPushButton#settings_btn:hover {{ border: 1px solid {accent}; }}"
            f"QTextEdit {{ background-color: transparent; border: none; color: {text_rgba}; }}"
        )
        
        self.layout = QVBoxLayout(self)
        
        # Tray reference (set later via set_tray())
        self._tray = None
        self._show_in_taskbar = self.config.ui_show_in_taskbar
        self._show_tray = self.config.ui_show_tray
        
        # --- Toolbar ---
        toolbar_layout = QHBoxLayout()
        
        self.activation_label = QLabel()
        toolbar_layout.addWidget(self.activation_label)
        
        toolbar_layout.addStretch()
        
        self.ind_user_mic = QPushButton()
        self.ind_sys_mic = QPushButton()
        self.ind_voice = QPushButton()
        
        # Connect clicks to signals
        # Use proper methods to prevent lambda garbage collection in PySide6
        self.ind_user_mic.clicked.connect(self._emit_user_mic)
        self.ind_sys_mic.clicked.connect(self._emit_sys_mic)
        self.ind_voice.clicked.connect(self._emit_voice)
        
        # Remove button borders and hover states by making cursor pointing hand
        self.ind_user_mic.setCursor(Qt.PointingHandCursor)
        self.ind_sys_mic.setCursor(Qt.PointingHandCursor)
        self.ind_voice.setCursor(Qt.PointingHandCursor)
        
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setObjectName("settings_btn")
        self.settings_btn.setFixedSize(85, 24)
        self.settings_btn.clicked.connect(self.open_settings)
        
        # Real-time Opacity (Occupancy) Container
        opacity_container = QWidget()
        opacity_container.setObjectName("OpacityContainer")
        opacity_container.setStyleSheet(f"#OpacityContainer {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; padding: 2px 8px; background-color: transparent; }}")
        
        opacity_layout = QHBoxLayout(opacity_container)
        opacity_layout.setContentsMargins(5, 2, 5, 2)
        opacity_layout.setSpacing(8)
        
        opacity_label = QLabel("Occupancy:")
        opacity_label.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {self.theme.get('base_text', '#E8E8E8')}; border: none;")
        
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(self.config.ui_opacity)
        self.opacity_slider.setFixedWidth(130) # Made the horizontal bar bigger
        self.opacity_slider.setToolTip("Adjust Voro Occupancy (Opacity)")
        self.opacity_slider.setCursor(Qt.PointingHandCursor)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        
        # Style the slider to look clean inside the container
        slider_color = "#4CAF50" if getattr(self, 'is_dark_mode', True) else "#388E3C"
        self.opacity_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                border: 1px solid #777;
                height: 4px;
                background: #444;
                margin: 2px 0;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {slider_color};
                border: 1px solid {slider_color};
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
        """)
        
        opacity_layout.addWidget(opacity_label)
        opacity_layout.addWidget(self.opacity_slider)
        
        toolbar_layout.addWidget(opacity_container)
        
        # Add spacing to take it a bit further from the mic/speaker buttons
        toolbar_layout.addSpacing(20)
        
        toolbar_layout.addWidget(self.ind_user_mic)
        toolbar_layout.addWidget(self.ind_sys_mic)
        toolbar_layout.addWidget(self.ind_voice)
        
        self.update_btn = QPushButton("Update Available")
        self.update_btn.setObjectName("update_btn")
        self.update_btn.setFixedSize(110, 24)
        self.update_btn.setStyleSheet(f"QPushButton {{ background-color: #2E7D32; color: white; border-radius: 6px; font-weight: bold; border: none; }} QPushButton:hover {{ background-color: #1B5E20; }}")
        self.update_btn.hide()
        self.update_btn.clicked.connect(self._prompt_update)
        toolbar_layout.addWidget(self.update_btn)
        
        toolbar_layout.addWidget(self.settings_btn)
        
        # Add Pin and Close buttons for the frameless window
        self.pin_btn = QPushButton("📌 Pin" if not self._always_on_top else "📌 Unpin")
        self.pin_btn.setFixedSize(65, 24)
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.setStyleSheet(f"QPushButton {{ background-color: transparent; border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; font-weight: bold; color: {self.theme['base_text']}; }} QPushButton:hover {{ background-color: #333; }}")
        self.pin_btn.clicked.connect(self.toggle_always_on_top)
        toolbar_layout.addWidget(self.pin_btn)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(30, 24)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet("QPushButton { background-color: #E53935; color: white; border-radius: 6px; font-weight: bold; border: none; } QPushButton:hover { background-color: #C62828; }")
        self.close_btn.clicked.connect(self.close)
        toolbar_layout.addWidget(self.close_btn)
        
        self._update_indicators()
        
        self.status_label = QLabel("Mic: INIT | AI: INIT | Privacy: INIT | State: IDLE")
        self.status_label.setStyleSheet(
            f"font-size: 11px; color: {self.theme['base_text']}; "
            f"margin-left: 5px; opacity: 0.85;"
        )
        
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setStyleSheet(
            f"font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;"
            f"font-size: {self.config.ui_font_size}px;"
            f"background-color: transparent;"
            f"color: {self.theme['base_text']};"
            f"border: none;"
            f"padding: 10px;"
        )
        
        self.layout.addLayout(toolbar_layout)
        self.layout.addWidget(self.status_label)
        self.layout.addWidget(self.text_area)
        
        # Signature
        self.sig_label = QLabel("Designed and Developed by <a href='https://nor-vi.in/' style='color:#0055A4; text-decoration:none;'>Norvi Agency</a>")
        self.sig_label.setOpenExternalLinks(True)
        self.sig_label.setAlignment(Qt.AlignRight)
        self.sig_label.setStyleSheet(f"font-size: 10px; color: {self.theme.get('base_text', '#888')}; opacity: 0.6; margin-right: 5px;")
        self.layout.addWidget(self.sig_label)

        
        self.current_mic = "READY"
        self.current_ai = "READY"
        self.current_privacy = "IDLE"
        self.current_state = "IDLE"
        
        # System Tray setup
        self._setup_tray()
        
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, self._init_updater)
        
        # --- Feature 4: Animated typing ---
        self._history_html = ""
        self._typing_full_text = ""
        self._typing_current_text = ""
        self._typing_index = 0
        self._typing_timer = QTimer(self)
        self._typing_timer.setInterval(15)
        self._typing_timer.timeout.connect(self._typing_tick)
        
        # Init label
        self.update_activation_label(getattr(self.config, 'activation_mode', 'basic'))
        
        # Shortcuts
        self.shortcut_clear = QShortcut(QKeySequence("Ctrl+R"), self)
        self.shortcut_clear.activated.connect(self.clear)
        
        self.shortcut_hide = QShortcut(QKeySequence("Esc"), self)
        self.shortcut_hide.activated.connect(self.hide)
        
        # Maximize Shortcut
        max_hotkey = getattr(self.config, 'ui_maximize_hotkey', 'F11')
        self.shortcut_maximize = QShortcut(QKeySequence(max_hotkey), self)
        self.shortcut_maximize.activated.connect(self.toggle_maximize)
        
        self.clear()
        self._apply_privacy_flag()
        self.tts_playlist = []
        self.audio_output = QAudioOutput(self)
        
        out_device_name = getattr(self.config, 'ui_tts_output_device', 'Default System Device')
        if out_device_name != "Default System Device":
            from PySide6.QtMultimedia import QMediaDevices
            for dev in QMediaDevices.audioOutputs():
                if dev.description() == out_device_name:
                    self.audio_output.setDevice(dev)
                    break
                    
        self.media_player = QMediaPlayer(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)

    
    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # --- Feature 2: Always-on-top toggle ---
    def toggle_always_on_top(self):
        from dotenv import set_key
        self._always_on_top = not self._always_on_top
        flags = Qt.Window
        if self._always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        
        icon_path = os.path.join(os.getcwd(), "logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.show()
        self.pin_btn.setText("ðŸ“Œ Unpin" if self._always_on_top else "ðŸ“Œ Pin")
        set_key(self._env_path, "UI_ALWAYS_ON_TOP", str(self._always_on_top))

    def _on_opacity_changed(self, value: int):
        # Update live opacity
        self.setWindowOpacity(value / 100.0)
        # Save to config object so Settings window reflects it if opened
        self.config.ui_opacity = value
        # Save securely to .env file for persistence
        from dotenv import set_key
        env_path = os.path.join(os.getcwd(), ".env")
        set_key(env_path, "UI_OPACITY", str(value))

    def set_tray(self, tray):
        """Called from main.py after the tray icon is created."""
        self._tray = tray
        # Apply saved tray visibility
        if self._show_tray:
            tray.show()
        else:
            tray.hide()
        # Apply saved taskbar visibility
        self._apply_taskbar_state()

    def _on_model_changed(self, new_model: str):
        if hasattr(self, 'bridge') and self.bridge:
            self.bridge.model_switched.emit(new_model)

    def toggle_taskbar_visibility(self):
        self._show_in_taskbar = not self._show_in_taskbar
        self._apply_taskbar_state()
        
        # Save real-time change to env so Settings dialog stays in sync
        import os
        from dotenv import set_key
        env_path = os.path.join(os.getcwd(), ".env")
        set_key(env_path, "UI_SHOW_IN_TASKBAR", str(self._show_in_taskbar))
        
        state = "SHOWN" if self._show_in_taskbar else "HIDDEN"
        if hasattr(self, 'bridge'):
            self.bridge.processing_state_updated.emit(f"TASKBAR {state}")
            self.bridge.config_updated.emit()
        else:
            self.update_processing_state(f"TASKBAR {state}")
        
    def toggle_tray_visibility(self):
        if not hasattr(self, 'tray_icon'): return
        self._show_tray = not getattr(self, '_show_tray', True)
        if self._show_tray:
            self.tray_icon.show()
        else:
            self.tray_icon.hide()
            
        import os
        from dotenv import set_key
        env_path = os.path.join(os.getcwd(), ".env")
        set_key(env_path, "UI_SHOW_TRAY", str(self._show_tray))
        
        state = "SHOWN" if self._show_tray else "HIDDEN"
        if hasattr(self, 'bridge'):
            self.bridge.processing_state_updated.emit(f"SYSTEM TRAY {state}")
            self.bridge.config_updated.emit()
        else:
            self.update_processing_state(f"SYSTEM TRAY {state}")

    def _apply_taskbar_state(self):
        """Show or hide the app in the Windows Taskbar using Qt WindowFlags."""
        # Save visibility state so we don't accidentally hide the window permanently
        was_visible = self.isVisible()
        
        # Base flags for our window
        flags = Qt.Window
        
        # Always on top hint
        if getattr(self, '_always_on_top', False):
            flags |= Qt.WindowStaysOnTopHint
            
        # Taskbar visibility (Qt.Tool hides from taskbar)
        if not self._show_in_taskbar:
            flags |= Qt.Tool
            
        self.setWindowFlags(flags)
        
        # Re-apply privacy flag because changing window flags can reset the window handle in PySide6
        self._apply_privacy_flag()

        
        if was_visible:
            self.show()

    def _apply_privacy_flag(self, stealth: bool = True):
        import sys
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = int(self.winId())
                # 0x11 = WDA_EXCLUDEFROMCAPTURE (invisible to screenshare/screenshot)
                # 0x00 = WDA_NONE (fully visible normal app)
                affinity = 0x11 if stealth else 0x00
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, affinity)
            except Exception as e:
                print(f"Could not set WDA: {e}")

        
    def _emit_user_mic(self, *args):
        self.user_mic_toggled.emit()
        
    def _emit_sys_mic(self, *args):
        self.sys_mic_toggled.emit()
        
    def _emit_voice(self, *args):
        self.tts_toggled.emit()

    def open_settings(self):
        self.settings_btn.setText("Loading...")
        self.settings_btn.setEnabled(False)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, self._open_settings_deferred)
        
    def _open_settings_deferred(self):
        from app.context.manager import ContextManager
        from app.ui.settings import SettingsDialog
        cm = ContextManager()
        dialog = SettingsDialog(cm, self)
        

        
        self.settings_btn.setText("Settings")
        self.settings_btn.setEnabled(True)
        if dialog.exec():
            if hasattr(self, 'bridge') and self.bridge:
                self.bridge.profile_updated.emit()
        
    def _update_indicators(self):
        from app.core.config import load_config
        self.config = load_config()
        
        c_on = "#00E676"  # Bright subtle green
        c_off = "#FF5252" # Soft red
        _is_dark = self.config.ui_theme_mode == 'dark' or (
            self.config.ui_theme_mode == 'system' and self.theme.get('bg', '#1E1E1E') == '#1E1E1E'
        )
        bg_col = "#2A2A2A" if _is_dark else "#E8E8E8"
        text_hover_col = "#EEE" if _is_dark else "#111" 
        
        if getattr(self.config, 'ui_show_tray', True):
            if hasattr(self, 'tray_icon') and not self.tray_icon.isVisible():
                self.tray_icon.show()
        else:
            if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
                self.tray_icon.hide()
                
        # We need a small fix to allow border-radius on QLabel without breaking background

        
        u_mic = not getattr(self.config, 'mute_user_mic', False)
        self.ind_user_mic.setText("🎙️")
        def style_btn(is_on):
            col = c_on if is_on else c_off
            return f"QPushButton {{ font-size: 14px; padding: 3px 8px; border-radius: 10px; background-color: {bg_col}; margin-right: 4px; color: {col}; border: 1px solid {col}; }} QPushButton:hover {{ background-color: {col}; color: {text_hover_col}; }}"
            
        self.ind_user_mic.setStyleSheet(style_btn(u_mic))
        self.ind_user_mic.setToolTip("User Microphone (Click to toggle)")
        
        s_mic = not getattr(self.config, 'mute_system_audio', False)
        self.ind_sys_mic.setText("🎧")
        self.ind_sys_mic.setStyleSheet(style_btn(s_mic))
        self.ind_sys_mic.setToolTip("System Audio Capture (Click to toggle)")
        
        v_voice = not getattr(self.config, 'ui_tts_muted', False)
        self.ind_voice.setText("🔊" if v_voice else "🔈")
        
        v_style = style_btn(v_voice).replace("margin-right: 4px;", "margin-right: 12px;")
        self.ind_voice.setStyleSheet(v_style)
        self.ind_voice.setToolTip("Voro Voice Output")

    def update_activation_label(self, mode: str):
        self.activation_label.setText(' Norvi Agent ')
        self.activation_label.setStyleSheet(
            'font-size: 11px; color: white; background-color: #0055A4; '
            'font-weight: bold; padding: 2px 8px; border-radius: 8px; margin-right: 6px;'
        )
    def _update_status_bar(self):
        self.status_label.setText(
            f"Mic: {self.current_mic} | AI: {self.current_ai} | Privacy: {self.current_privacy} | State: {self.current_state}"
        )
        
    def update_mic_status(self, text: str):
        self.current_mic = text
        self._update_status_bar()
        
    def update_ai_status(self, text: str):
        self.current_ai = text
        self._update_status_bar()
        
    def update_privacy_status(self, text: str):
        self.current_privacy = text
        self._update_status_bar()

    def update_processing_state(self, text: str):
        self.current_state = text
        self._update_status_bar()
        

    def _update_html_safe(self, html_content: str):
        scrollbar = self.text_area.verticalScrollBar()
        # Consider it at bottom if within 15 pixels
        was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 15
        prev_value = scrollbar.value()
        
        self.text_area.setHtml(html_content)
        
        if was_at_bottom:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(prev_value)
            
        if not self.isVisible():
            self.show()

    def _append_html(self, html: str):
        self._history_html += html
        self._update_html_safe(self._history_html)

    def update_user_input(self, text: str):
        """Displays the STT transcript as a USER message."""
        import re
        from app.core.config import load_config

        match = re.match(r'^\[(.*?)\]:\s*(.*)$', text, re.DOTALL)
        if match:
            speaker = match.group(1).upper()
            text_body = match.group(2).replace('\n', '<br>')
        else:
            speaker = "YOU"
            text_body = text.replace('\n', '<br>')

        # Pick heading colour from config
        self.config = load_config()
        if speaker == "INTERVIEWER":
            heading_col = getattr(self.config, 'ui_interviewer_heading_color', '#FF9900')
        else:
            heading_col = getattr(self.config, 'ui_you_heading_color', '#E53935')

        # Body text: theme-aware contrast
        is_dark = self.theme.get('bg', '#1E1E1E') == '#1E1E1E'
        body_text_col = "#F0F0F0" if is_dark else "#1A1A1A"
        fs = self.config.ui_font_size

        html = f'''
        <div style="margin-top: 10px; margin-bottom: 15px;">
            <span style="color: {heading_col}; font-size: {fs}px; font-weight: 700;
                text-transform: uppercase; letter-spacing: 1px;">{speaker}</span><br>
            <span style="color: {body_text_col}; font-size: {fs}px; line-height: 1.4;">{text_body}</span>
        </div>
        '''
        self._append_html(html)

    # --- Feature 4: Code Syntax Highlighting & Markdown ---
    def update_answer(self, text: str):
        """Starts the typing animation for the AI response."""
        self._typing_timer.stop()
        self._typing_full_text = text
        self._typing_current_text = ""
        self._typing_index = 0
        self._typing_timer.start(15)
        self.update_processing_state("TYPING")
        
    def update_answer_chunk(self, chunk: str, is_first: bool = False, is_last: bool = False):
        if is_first:
            self._typing_timer.stop()
            self._typing_current_text = chunk
            self.update_processing_state("GENERATING")
        else:
            self._typing_current_text += chunk
            
        # color unused - body text now uses theme-aware body_text_col computed below
        fs = self.config.ui_font_size
        
        try:
            import markdown
            from pygments.formatters import HtmlFormatter
            md_html = markdown.markdown(self._typing_current_text, extensions=['fenced_code', 'codehilite'])
            style = 'monokai' if self.config.ui_theme_mode == 'dark' else 'default'
            css = HtmlFormatter(style=style).get_style_defs('.codehilite')
        except Exception:
            md_html = self._typing_current_text.replace('\n', '<br>')
            css = ""
            
        voro_heading_col = getattr(self.config, 'ui_voro_heading_color', '#0055A4')
        is_dark_mode = self.theme.get('bg', '#1E1E1E') == '#1E1E1E'
        body_text_col = "#F0F0F0" if is_dark_mode else "#1A1A1A"
        code_bg = "#1A1B26" if is_dark_mode else "#F0F4F8"
        
        final_html = f'''
        <div style="margin-bottom: 15px; border-left: 3px solid {voro_heading_col}; padding-left: 10px;">
            <style>
                {css}
                .codehilite {{ background-color: {code_bg}; padding: 10px; border-radius: 6px; font-family: 'Consolas', 'Courier New', monospace; font-size: {fs-1}px; }}
                p {{ margin-top: 4px; margin-bottom: 4px; line-height: 1.5; }}
                ul {{ margin-top: 4px; margin-bottom: 4px; padding-left: 20px; }}
                strong {{ color: {voro_heading_col}; }}
                em {{ color: {body_text_col}; opacity: 0.85; }}
            </style>
            <span style="color: {voro_heading_col}; font-weight: 700; font-size: {fs}px; text-transform: uppercase; letter-spacing: 1px;">Voro</span>
            <div style="color: {body_text_col}; font-size: {fs}px; margin-top: 2px;">
                {md_html}
            </div>
        </div>
        '''
        
        self._update_html_safe(self._history_html + final_html)
            
        if is_last:
            self._history_html += final_html
            self.update_processing_state("IDLE")

    def _typing_tick(self):
        chunk_size = max(1, len(self._typing_full_text) // 50) # dynamic speed
        self._typing_current_text += self._typing_full_text[self._typing_index : self._typing_index + chunk_size]
        self._typing_index += chunk_size
        
        # color unused - body text now uses theme-aware body_text_col computed below
        fs = self.config.ui_font_size
        
        try:
            import markdown
            from pygments.formatters import HtmlFormatter
            md_html = markdown.markdown(self._typing_current_text, extensions=['fenced_code', 'codehilite'])
            style = 'monokai' if self.config.ui_theme_mode == 'dark' else 'default'
            css = HtmlFormatter(style=style).get_style_defs('.codehilite')
        except Exception:
            md_html = self._typing_current_text.replace('\n', '<br>')
            css = ""
            
        voro_heading_col = getattr(self.config, 'ui_voro_heading_color', '#0055A4')
        is_dark_mode = self.theme.get('bg', '#1E1E1E') == '#1E1E1E'
        body_text_col = "#F0F0F0" if is_dark_mode else "#1A1A1A"
        code_bg = "#1A1B26" if is_dark_mode else "#F0F4F8"
        
        final_html = f'''
        <div style="margin-bottom: 15px; border-left: 3px solid {voro_heading_col}; padding-left: 10px;">
            <style>
                {css}
                .codehilite {{ background-color: {code_bg}; padding: 10px; border-radius: 6px; font-family: 'Consolas', 'Courier New', monospace; font-size: {fs-1}px; }}
                p {{ margin-top: 4px; margin-bottom: 4px; line-height: 1.5; }}
                ul {{ margin-top: 4px; margin-bottom: 4px; padding-left: 20px; }}
                strong {{ color: {voro_heading_col}; }}
                em {{ color: {body_text_col}; opacity: 0.85; }}
            </style>
            <span style="color: {voro_heading_col}; font-weight: 700; font-size: {fs}px; text-transform: uppercase; letter-spacing: 1px;">Voro</span>
            <div style="color: {body_text_col}; font-size: {fs}px; margin-top: 2px;">
                {md_html}
            </div>
        </div>
        '''
        
        self._update_html_safe(self._history_html + final_html)
            
        if self._typing_index >= len(self._typing_full_text):
            self._typing_timer.stop()
            self._history_html += final_html
            self.update_processing_state("IDLE")

    def update_error(self, text: str):
        """Displays an error message."""
        text_html = text.replace('\n', '<br>')
        html = f'<div style="margin-bottom: 4px;"><span style="color: #D32F2F; font-weight: bold;">VORO ERROR</span><br><span style="color: #D32F2F;">{text_html}</span></div>'
        self._append_html(html)
        self.update_processing_state("IDLE")

    def clear(self):
        self._typing_timer.stop()
        self._history_html = ""
        self.text_area.setPlainText("")

    # --- Feature 5: Minimize to tray ---
    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                self.hide()
        super().changeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    # --- Feature 3: Save geometry on close ---
    def closeEvent(self, event):
        """Save window position and quit."""
        from dotenv import set_key
        from PySide6.QtWidgets import QApplication
        if self.config.ui_remember_position:
            geo = self.geometry()
            set_key(self._env_path, "UI_WIN_X", str(geo.x()))
            set_key(self._env_path, "UI_WIN_Y", str(geo.y()))
            set_key(self._env_path, "UI_WIN_W", str(geo.width()))
            set_key(self._env_path, "UI_WIN_H", str(geo.height()))
        app = QApplication.instance()
        if app:
            app.quit()
        event.accept()

    def showEvent(self, event):
        """Guarantee privacy flag is re-applied every time window is shown."""
        super().showEvent(event)
        # Re-apply privacy flag respecting current stealth state
        self._apply_privacy_flag(stealth=getattr(self, '_stealth_active', True))

        
    def toggle_stealth_mode(self):
        '''Toggle Stealth Mode: ON = ghost to screenshare/screenshot. OFF = fully normal visible app.'''
        self._stealth_active = not getattr(self, '_stealth_active', False)
        if self._stealth_active:
            # Stealth ON: Invisible to screenshare/screenshot but user can still see Voro
            # Also hide tray + taskbar for full invisibility
            self._apply_privacy_flag(stealth=True)
            self._show_tray = False
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.hide()
            self._show_in_taskbar = False
            self._apply_taskbar_state()
        else:
            # Stealth OFF: Fully normal visible app - appears in screenshare, screenshots, taskbar, tray
            self._apply_privacy_flag(stealth=False)
            self._show_tray = True
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.show()
            self._show_in_taskbar = getattr(self.config, 'ui_show_in_taskbar', False)
            self._apply_taskbar_state()
            if not self.isVisible():
                self.show()
            self.activateWindow()

    def toggle_visibility(self):
        """Global hotkey handler to show/hide the assistant."""
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()
            self.raise_()

    def play_tts_audio(self, filepath: str):
        self.tts_playlist.append(filepath)
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self._play_next_tts()

    def _play_next_tts(self):
        if self.tts_playlist:
            filepath = self.tts_playlist.pop(0)
            
            # Apply user volume setting
            vol = getattr(self.config, 'ui_tts_volume', 100)
            self.audio_output.setVolume(vol / 100.0)
            
            # Set source and let LoadedMedia signal trigger play() for safety
            self.media_player.setSource(QUrl.fromLocalFile(filepath))
            
    def _on_playback_state_changed(self, state):
        import os
        from PySide6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlaybackState.PlayingState:
            os.environ["VORO_IS_SPEAKING"] = "True"
        else:
            os.environ["VORO_IS_SPEAKING"] = "False"

    def _on_media_status_changed(self, status):
        from PySide6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            # Delete file after playing
            source = self.media_player.source().toLocalFile()
            import os
            if source and os.path.exists(source):
                try:
                    os.remove(source)
                except Exception:
                    pass
            self._play_next_tts()
        elif status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.media_player.play()

    def stop_tts_audio(self):
        self.media_player.stop()
        for f in self.tts_playlist:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass
        self.tts_playlist.clear()

    def _setup_tray(self):
        # Only show tray if configured (or default to true)
        self.tray_icon = QSystemTrayIcon(self)
        import os
        icon_path = os.path.join(os.getcwd(), "logo.ico")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
            
        # Create menu
        tray_menu = QMenu(self)
        
        bg = self.theme.get('bg', '#1E1E1E')
        text_col = self.theme.get('base_text', '#FFFFFF')
        border = self.theme.get('border', '#444444')
        hover_bg = "#3A3A3A" if bg.upper() in ["#1E1E1E", "#000000"] else "#E0E0E0"
        
        tray_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {bg};
                color: {text_col};
                border: 1px solid {border};
            }}
            QMenu::item {{
                padding: 6px 24px 6px 24px;
                background: transparent;
            }}
            QMenu::item:selected {{
                background-color: {hover_bg};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {border};
                margin: 4px 0px 4px 0px;
            }}
        """)
        
        show_action = tray_menu.addAction("Show Voro")
        show_action.triggered.connect(self.showNormal)
        
        settings_action = tray_menu.addAction("Settings")
        settings_action.triggered.connect(self.open_settings)
        
        tray_menu.addSeparator()
        
        restart_action = tray_menu.addAction("Restart")
        restart_action.triggered.connect(self._tray_restart)
        
        quit_action = tray_menu.addAction("Quit Voro")
        quit_action.triggered.connect(self._tray_quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        # Double click to show
        self.tray_icon.activated.connect(self._tray_activated)
        
        if getattr(self.config, 'ui_show_tray', True):
            self.tray_icon.show()
            
    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def _tray_restart(self):
        import sys, subprocess, os
        from dotenv import dotenv_values
        
        env_path = os.path.join(os.getcwd(), ".env")
        new_env = os.environ.copy()
        if os.path.exists(env_path):
            new_env.update(dotenv_values(env_path))
            
        if getattr(sys, 'frozen', False):
            subprocess.Popen([sys.executable], env=new_env)
        else:
            subprocess.Popen([sys.executable, "main.py"], env=new_env)
            
        if hasattr(self, 'bridge'):
            self.bridge.quit_application.emit()
        else:
            QApplication.quit()

    def _tray_quit(self):
        # Emit the quit signal via bridge
        if hasattr(self, 'bridge'):
            self.bridge.quit_application.emit()
        else:
            QApplication.quit()
    def _init_updater(self):
        from app.core.updater import Updater
        self.updater = Updater()
        self.updater.update_available.connect(self._on_update_available)
        self.updater.download_progress.connect(self._on_download_progress)
        self.updater.download_complete.connect(self._on_download_complete)
        self.updater.download_error.connect(self._on_download_error)
        if getattr(self.config, 'ui_auto_update', True) in [True, "True", "true"]:
            self.updater.check_for_updates()
        
    def _on_update_available(self, version, notes, url):
        self._update_version = version
        self._update_notes = notes
        self._update_url = url
        self.update_btn.show()
        
    def _prompt_update(self):
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "Update Voro", f"Version {self._update_version} is available!\n\nRelease Notes:\n{self._update_notes}\n\nDo you want to download and install it now?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.update_btn.setEnabled(False)
            self.updater.download_and_install(self._update_url)
            
    def _on_download_progress(self, progress):
        self.update_btn.setText(f"D/L: {progress}%")
        
    def _on_download_complete(self, path):
        self.update_btn.setText("Installing...")
        
    def _on_download_error(self, err):
        self.update_btn.setText("Failed")
        self.update_btn.setEnabled(True)
