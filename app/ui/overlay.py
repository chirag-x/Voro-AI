from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl
import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton
from PySide6.QtCore import Qt, QObject, Signal, QTimer
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
        flags = Qt.Window
        if self._always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        
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
        
        # Apply Opacity
        self.setWindowOpacity(self.config.ui_opacity / 100.0)
        
        # Apply theme
        self.setStyleSheet(
            f"QWidget {{ font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; }}"
            f"OverlayWindow {{ background-color: {self.theme['bg']}; border-radius: 12px; border: 1px solid #444; }}"
            f"QLabel {{ color: {self.theme['base_text']}; }}"
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
        self.settings_btn.setFixedSize(60, 24)
        self.settings_btn.clicked.connect(self.open_settings)
        
        toolbar_layout.addWidget(self.ind_user_mic)
        toolbar_layout.addWidget(self.ind_sys_mic)
        toolbar_layout.addWidget(self.ind_voice)
        toolbar_layout.addWidget(self.settings_btn)
        
        self._update_indicators()
        
        self.status_label = QLabel("Mic: INIT | AI: INIT | Privacy: INIT | State: IDLE")
        self.status_label.setStyleSheet("font-size: 11px; color: #888; margin-left: 5px;")
        
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
        
        self.current_mic = "READY"
        self.current_ai = "READY"
        self.current_privacy = "IDLE"
        self.current_state = "IDLE"
        
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
        self.show()
        self.pin_btn.setText("ðŸ“Œ Unpin" if self._always_on_top else "ðŸ“Œ Pin")
        set_key(self._env_path, "UI_ALWAYS_ON_TOP", str(self._always_on_top))

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
        self.update_processing_state(f"TASKBAR {state}")
        
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
        self.tts_playlist = []
        self.audio_output = QAudioOutput(self)
        self.media_player = QMediaPlayer(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)

        
        if was_visible:
            self.show()

    def _apply_privacy_flag(self):
        import sys
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = int(self.winId())
                WDA_EXCLUDEFROMCAPTURE = 0x11
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
            except Exception as e:
                print(f"Could not set WDA_EXCLUDEFROMCAPTURE: {e}")
        
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
        bg_col = "#2A2A2A" if self.config.ui_theme_mode == 'dark' else "#E0E0E0"
        
        # We need a small fix to allow border-radius on QLabel without breaking background

        
        u_mic = not getattr(self.config, 'mute_user_mic', False)
        self.ind_user_mic.setText("🎙️")
        def style_btn(is_on):
            col = c_on if is_on else c_off
            return f"QPushButton {{ font-size: 14px; padding: 3px 8px; border-radius: 10px; background-color: {bg_col}; margin-right: 4px; color: {col}; border: 1px solid {col}; }} QPushButton:hover {{ background-color: {col}; color: #111; }}"
            
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
        if mode == 'premium':
            self.activation_label.setText("Premium Mode")
            self.activation_label.setStyleSheet("font-size: 11px; color: #FFD700; font-weight: bold; padding-right: 10px;") # Gold
        elif mode == 'local':
            self.activation_label.setText("Local Mode")
            self.activation_label.setStyleSheet("font-size: 11px; color: #00FF00; font-weight: bold; padding-right: 10px;") # Green
        else:
            self.activation_label.setText("Basic Mode")
            self.activation_label.setStyleSheet(f"font-size: 11px; color: {self.theme['base_text']}; font-weight: bold; padding-right: 10px;")
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
        
    def _append_html(self, html: str):
        self._history_html += html
        self.text_area.setHtml(self._history_html)
        scrollbar = self.text_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        if not self.isVisible():
            self.show()

    def update_user_input(self, text: str):
        """Displays the STT transcript as a USER message."""
        color = self.config.ui_question_color
        import re
        match = re.match(r'^\[(.*?)\]:\s*(.*)$', text, re.DOTALL)
        if match:
            speaker = match.group(1).upper()
            text_html = match.group(2).replace('\n', '<br>')
            if speaker == "INTERVIEWER":
                color = "#FF9900"
        else:
            speaker = "YOU"
            text_html = text.replace('\n', '<br>')

        # Modern User Bubble Style
        html = f'''
        <div style="margin-top: 10px; margin-bottom: 15px;">
            <span style="color: {color}; font-size: {self.config.ui_font_size}px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;">{speaker}</span><br>
            <span style="color: #FFFFFF; font-size: {self.config.ui_font_size}px; line-height: 1.4;">{text_html}</span>
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
            
        color = self.config.ui_answer_color
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
            
        final_html = f'''
        <div style="margin-bottom: 15px; border-left: 3px solid #0055A4; padding-left: 10px;">
            <style>
                {css}
                .codehilite {{ background-color: #1A1B26; padding: 10px; border-radius: 6px; font-family: 'Consolas', 'Courier New', monospace; font-size: {fs-1}px; }}
                p {{ margin-top: 4px; margin-bottom: 4px; line-height: 1.5; }}
                ul {{ margin-top: 4px; margin-bottom: 4px; padding-left: 20px; }}
            </style>
            <span style="color: #0055A4; font-weight: 700; font-size: {fs}px; text-transform: uppercase; letter-spacing: 1px;">Voro</span>
            <div style="color: {color}; font-size: {fs}px; margin-top: 2px;">
                {md_html}
            </div>
        </div>
        '''
        
        self.text_area.setHtml(self._history_html + final_html)
        scrollbar = self.text_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        if not self.isVisible():
            self.show()
            
        if is_last:
            self._history_html += final_html
            self.update_processing_state("IDLE")

    def _typing_tick(self):
        chunk_size = max(1, len(self._typing_full_text) // 50) # dynamic speed
        self._typing_current_text += self._typing_full_text[self._typing_index : self._typing_index + chunk_size]
        self._typing_index += chunk_size
        
        color = self.config.ui_answer_color
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
            
        final_html = f'''
        <div style="margin-bottom: 15px; border-left: 3px solid #0055A4; padding-left: 10px;">
            <style>
                {css}
                .codehilite {{ background-color: #1A1B26; padding: 10px; border-radius: 6px; font-family: 'Consolas', 'Courier New', monospace; font-size: {fs-1}px; }}
                p {{ margin-top: 4px; margin-bottom: 4px; line-height: 1.5; }}
                ul {{ margin-top: 4px; margin-bottom: 4px; padding-left: 20px; }}
            </style>
            <span style="color: #0055A4; font-weight: 700; font-size: {fs}px; text-transform: uppercase; letter-spacing: 1px;">Voro</span>
            <div style="color: {color}; font-size: {fs}px; margin-top: 2px;">
                {md_html}
            </div>
        </div>
        '''
        
        self.text_area.setHtml(self._history_html + final_html)
        scrollbar = self.text_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        if not self.isVisible():
            self.show()
            
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
        self._apply_privacy_flag()
        self.tts_playlist = []
        self.audio_output = QAudioOutput(self)
        self.media_player = QMediaPlayer(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)

        
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
            self.media_player.setSource(QUrl.fromLocalFile(filepath))
            
            # Apply user volume setting
            vol = getattr(self.config, 'ui_tts_volume', 100)
            self.audio_output.setVolume(vol / 100.0)
            
            self.media_player.play()
            
    def _on_playback_state_changed(self, state):
        import os
        from PySide6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlaybackState.PlayingState:
            os.environ["VORO_IS_SPEAKING"] = "True"
        else:
            os.environ["VORO_IS_SPEAKING"] = "False"

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            # Delete file after playing
            source = self.media_player.source().toLocalFile()
            if source and os.path.exists(source):
                try:
                    os.remove(source)
                except:
                    pass
            self._play_next_tts()

    def stop_tts_audio(self):
        self.media_player.stop()
        for f in self.tts_playlist:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
        self.tts_playlist.clear()
