from PySide6.QtCore import Slot
import os
import sys
from dotenv import set_key
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QMessageBox, QSlider, QColorDialog,
                               QListWidget, QStackedWidget, QWidget, QCheckBox, QComboBox, QTextEdit, QScrollArea,
                               QRadioButton, QGroupBox, QButtonGroup)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from app.core.config import load_config
from app.context.manager import ContextManager

class NoScrollComboBox(QComboBox):
    def wheelEvent(self, e):
        e.ignore()
class NoScrollSlider(QSlider):
    def wheelEvent(self, e):
        e.ignore()

class ValidatorThread(QThread):
    result_ready = Signal(str, bool, str)
    finished_validation = Signal()

    def __init__(self, api_key, models, base_url):
        super().__init__()
        self.api_key = api_key
        self.models = models
        self.base_url = base_url

    def run(self):
        import httpx
        client = httpx.Client(timeout=10.0)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/Voro",
            "X-Title": "Voro Validation"
        }
        for m in self.models:
            if not m.strip():
                continue
            payload = {
                "model": m.strip(),
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1
            }
            try:
                resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                if resp.status_code == 200:
                    self.result_ready.emit(m.strip(), True, "")
                else:
                    self.result_ready.emit(m.strip(), False, f"HTTP {resp.status_code}")
            except Exception as e:
                self.result_ready.emit(m.strip(), False, str(e))
        self.finished_validation.emit()


def _make_section_header(title: str, theme: dict) -> "QLabel":
    """Create a bold themed section header label."""
    from PySide6.QtWidgets import QLabel
    lbl = QLabel(f"<b>{title}</b>")
    lbl.setStyleSheet(
        f"font-size: 16px; color: #0055A4; padding: 6px 0 2px 0; "
        f"border-bottom: 1px solid {theme.get('border', '#444')}; margin-bottom: 4px;"
    )
    return lbl


import threading
import time
from PySide6.QtCore import QThread, Signal
from huggingface_hub import snapshot_download
import huggingface_hub.utils as hf_utils
from tqdm.auto import tqdm as std_tqdm

class ModelDownloadThread(QThread):
    progress = Signal(int, int, str) # downloaded, total, msg
    finished = Signal(bool, str) # success, error_msg

    def __init__(self, model_size, download_dir):
        super().__init__()
        self.model_size = model_size
        self.download_dir = download_dir
        self.is_paused = False
        self.is_cancelled = False
        self._orig_tqdm = hf_utils.tqdm

    def run(self):
        repo_id = f"Systran/faster-whisper-{self.model_size}"
        if self.model_size == "large":
            repo_id = "Systran/faster-whisper-large-v3"
        elif self.model_size == "small":
            repo_id = "Systran/faster-whisper-base"
        elif self.model_size == "small.en":
            repo_id = "Systran/faster-whisper-base.en"
            
        outer_self = self
        
        class CustomTqdm(std_tqdm):
            def __init__(self, *args, **kwargs):
                class DummyFile:
                    def write(self, x): pass
                    def flush(self): pass
                kwargs['file'] = DummyFile()
                super().__init__(*args, **kwargs)
                
            def update(self, n=1):
                if outer_self.is_cancelled:
                    raise InterruptedError("Download cancelled by user.")
                while outer_self.is_paused and not outer_self.is_cancelled:
                    time.sleep(0.5)
                if outer_self.is_cancelled:
                    raise InterruptedError("Download cancelled by user.")
                
                super().update(n)
                
                # Check if it's tracking bytes (not files) by inspecting self.unit
                unit = getattr(self, 'unit', '').lower()
                if unit in ['b', 'ib', 'bytes'] and self.total is not None and self.total > 10 * 1024 * 1024:
                    msg = f"Downloading... {self.n/1024/1024:.1f}MB / {self.total/1024/1024:.1f}MB"
                    outer_self.progress.emit(self.n, self.total, msg)
        
        try:
            hf_utils.tqdm = CustomTqdm
            
            import os
            base_dir = self.download_dir if self.download_dir.strip() else os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
            target_dir = os.path.join(base_dir, f"faster-whisper-{self.model_size}")
            os.makedirs(target_dir, exist_ok=True)
            
            snapshot_download(repo_id=repo_id, local_dir=target_dir, local_dir_use_symlinks=False)
            
            self.finished.emit(True, f"Saved to {target_dir}")
        except InterruptedError as e:
            self.finished.emit(False, str(e))
        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            hf_utils.tqdm = self._orig_tqdm

class CollapsibleBox(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.toggle_button = QPushButton(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 12px 15px;
                background-color: #2D333B;
                color: #FFFFFF;
                border: 1px solid #444C56;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #373E47;
            }
            QPushButton:checked {
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                border-bottom: none;
                background-color: #1E2329;
            }
        """)
        
        self.content_area = QWidget()
        self.content_area.setStyleSheet("""
            QWidget#content_area {
                background-color: transparent;
                border: 1px solid #444C56;
                border-top: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }
        """)
        self.content_area.setObjectName("content_area")
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(10)
        self.content_area.setVisible(False)
        
        self.toggle_button.toggled.connect(self.content_area.setVisible)
        
        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)
        
    def addWidget(self, widget):
        self.content_layout.addWidget(widget)
        
    def addLayout(self, layout):
        self.content_layout.addLayout(layout)

class SettingsDialog(QDialog):
    def __init__(self, context_manager: ContextManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Voro Settings")
        
        self.config = load_config()
        if self.config.ui_settings_win_x != -1:
            self.setGeometry(
                self.config.ui_settings_win_x,
                self.config.ui_settings_win_y,
                self.config.ui_settings_win_w,
                self.config.ui_settings_win_h
            )
        else:
            self.resize(900, 650)
        self.context_manager = context_manager
        self.env_path = os.path.join(os.getcwd(), ".env")
        
        # Auto-detect Windows theme
        from app.ui.theme import get_theme_colors
        self.theme = get_theme_colors(self.config.ui_theme_mode)
        
        # Modern Settings QSS — all colours are theme-aware
        is_dark = self.config.ui_theme_mode == 'dark' or (
            self.config.ui_theme_mode == 'system' and self.theme['bg'] == '#1E1E1E'
        )
        bg_main = self.theme['bg']
        bg_card          = "#2A2A2A"   if is_dark else "#F0F0F0"
        bg_card_hover    = "#333333"   if is_dark else "#E0E0E0"
        btn_bg           = "#3A3A3A"   if is_dark else "#E0E0E0"
        btn_border       = "#555"      if is_dark else "#BBBBBB"
        btn_hover_bg     = "#484848"   if is_dark else "#CCCCCC"
        input_bg         = "#1E1E1E"   if is_dark else "#FFFFFF"
        input_border     = "#555"      if is_dark else "#CCCCCC"
        chk_bg           = "#333"      if is_dark else "#CCCCCC"
        chk_border       = "#666"      if is_dark else "#999999"
        chk_hover        = "#444"      if is_dark else "#BBBBBB"
        slider_groove    = "#444"      if is_dark else "#CCCCCC"
        group_border     = "#404040"   if is_dark else "#CCCCCC"
        text_col         = self.theme['base_text']
        accent           = "#0055A4"

        modern_qss = f"""
        QDialog {{
            background-color: {bg_main};
            color: {text_col};
            font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            font-size: 15px;
        }}
        QWidget {{
            color: {text_col};
        }}
        QListWidget {{
            background-color: {bg_main};
            border: none;
            outline: none;
            padding: 10px 5px;
            color: {text_col};
        }}
        QListWidget::item {{
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 2px;
            color: {text_col};
        }}
        QListWidget::item:hover {{
            background-color: {bg_card_hover};
        }}
        QListWidget::item:selected {{
            background-color: {accent};
            color: white;
            font-weight: bold;
        }}
        QGroupBox {{
            background-color: {bg_card};
            border-radius: 10px;
            margin-top: 15px;
            padding-top: 25px;
            border: 1px solid {group_border};
            color: {text_col};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 5px 10px;
            font-weight: bold;
            font-size: 14px;
            color: {accent};
        }}
        QPushButton {{
            background-color: {btn_bg};
            color: {text_col};
            border-radius: 6px;
            padding: 6px 12px;
            border: 1px solid {btn_border};
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {btn_hover_bg};
            border: 1px solid {accent};
        }}
        QPushButton[class="primary"] {{
            background-color: {accent};
            color: white;
            border: none;
        }}
        QPushButton[class="primary"]:hover {{
            background-color: #0066CC;
        }}
        QLineEdit, QComboBox, NoScrollComboBox {{
            background-color: {input_bg};
            border: 1px solid {input_border};
            border-radius: 4px;
            padding: 5px;
            color: {text_col};
        }}
        QComboBox QAbstractItemView, NoScrollComboBox QAbstractItemView {{
            background-color: {input_bg};
            color: {text_col};
            selection-background-color: {accent};
            selection-color: white;
        }}
        QLineEdit:focus, QComboBox:focus, NoScrollComboBox:focus {{
            border: 1px solid {accent};
        }}
        QCheckBox {{
            color: {text_col};
        }}
        QCheckBox::indicator {{
            width: 32px;
            height: 18px;
            border-radius: 9px;
            border: 1px solid {chk_border};
            background-color: {chk_bg};
        }}
        QCheckBox::indicator:checked {{
            background-color: {accent};
            border: 1px solid {accent};
        }}
        QCheckBox::indicator:unchecked:hover {{
            background-color: {chk_hover};
        }}
        QSlider::groove:horizontal {{
            height: 6px;
            background: {slider_groove};
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {accent};
            width: 14px;
            height: 14px;
            margin: -4px 0;
            border-radius: 7px;
        }}
        QSlider::sub-page:horizontal {{
            background: {accent};
            border-radius: 3px;
        }}
        QLabel {{
            color: {text_col};
        }}
        QScrollArea {{
            border: none;
            background-color: transparent;
        }}
        QScrollArea > QWidget > QWidget {{
            background-color: {bg_card};
            color: {text_col};
        }}
        QScrollArea QWidget {{
            color: {text_col};
        }}
        QAbstractScrollArea::viewport {{
            background-color: {bg_card};
        }}
        QTextEdit {{
            background-color: {input_bg};
            color: {text_col};
            border: 1px solid {input_border};
            border-radius: 4px;
        }}
        QRadioButton {{
            color: {text_col};
        }}
        QStackedWidget {{
            background-color: {bg_card};
        }}
        """
        self.setStyleSheet(modern_qss)
        
        # Main Layout: Sidebar + Stacked Widget
        outer_layout = QHBoxLayout(self)
        
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(150)
        self.sidebar.addItems(["Norvi", "Interface", "Vision", "Audio", "Profile", "Company Info", "Other", "Updates", "Help"])
        self.sidebar.currentRowChanged.connect(self.change_page)
        outer_layout.addWidget(self.sidebar)
        
        right_layout = QVBoxLayout()
        self.pages = QStackedWidget()
        right_layout.addWidget(self.pages)
        
        # Setup Pages
        self.setup_norvi_page()
        self.setup_window_page()
        self.setup_vision_page()
        self.setup_audio_page()
        self.setup_profile_page()
        self.setup_company_page()
        self.setup_other_page()
        self.setup_updates_page()
        self.setup_help_page()
        
        # Initialize UI fields with current context (must happen after all pages exist)
        self.load_profile_fields(self.context_manager.active_profile_name)
        self._last_selected_profile = self.context_manager.active_profile_name
        
        # Signature
        self.sig_label = QLabel("Designed and Developed by <a href='https://nor-vi.in/' style='color:#0055A4; text-decoration:none;'>Norvi Agency</a>")
        self.sig_label.setOpenExternalLinks(True)
        self.sig_label.setAlignment(Qt.AlignRight)
        self.sig_label.setStyleSheet(f"font-size: 11px; color: {self.theme.get('base_text', '#888')}; margin-bottom: 10px;")
        right_layout.addWidget(self.sig_label)
        
        # Action Buttons (Bottom)
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save & Restart")
        save_btn.setProperty("class", "primary")
        save_btn.clicked.connect(self.save_settings)
        close_btn = QPushButton("Cancel")
        close_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(close_btn)
        right_layout.addLayout(btn_layout)
        
        outer_layout.addLayout(right_layout)
        
        # Privacy flag is only applied by OverlayWindow, not the settings dialog
        
    def change_page(self, index):
        self.pages.setCurrentIndex(index)
        





    def _create_hk_input(self, default_val):
        from PySide6.QtWidgets import QKeySequenceEdit, QPushButton, QWidget, QHBoxLayout
        from PySide6.QtGui import QKeySequence
        from PySide6.QtCore import Qt
        
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        seq_str = str(default_val).title()
        hk = QKeySequenceEdit(QKeySequence(seq_str))
        hk.setFixedWidth(120)
        
        # Prevent accidental edits while keeping normal appearance
        hk.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        hk.setFocusPolicy(Qt.NoFocus)
        
        btn = QPushButton("Edit")
        btn.setFixedWidth(50)
        btn.setCursor(Qt.PointingHandCursor)
        
        def _on_btn_clicked():
            if btn.text() == "Edit":
                btn.setText("Save")
                btn.setStyleSheet("QPushButton { background-color: #0078D7; color: white; border: none; font-weight: bold; border-radius: 4px; padding: 2px; }")
                hk.setAttribute(Qt.WA_TransparentForMouseEvents, False)
                hk.setFocusPolicy(Qt.StrongFocus)
                hk.setFocus()
            else:
                btn.setText("Edit")
                btn.setStyleSheet("")
                hk.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                hk.setFocusPolicy(Qt.NoFocus)
                
        btn.clicked.connect(_on_btn_clicked)
        
        layout.addWidget(hk)
        layout.addWidget(btn)
        layout.addStretch()
        
        # Monkey-patch text() so the existing save logic works without modification
        container.text = lambda: hk.keySequence().toString(QKeySequence.PortableText).lower().replace('meta', 'win')
        # Handle setFixedWidth if it was called on the return value
        container.setFixedWidth = lambda w: None
        return container

    def _create_toggle_btn(self, default_checked, text_enabled, text_disabled, inverted=False):
        from PySide6.QtWidgets import QPushButton
        from PySide6.QtCore import Qt
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setChecked(default_checked)
        btn.setCursor(Qt.PointingHandCursor)
        def _update(checked):
            is_active = not checked if inverted else checked
            if is_active:
                btn.setText(text_enabled)
                btn.setStyleSheet("QPushButton { background-color: #0078D7; color: white; border: none; padding: 6px; border-radius: 4px; font-weight: bold; }")
            else:
                btn.setText(text_disabled)
                btn.setStyleSheet("QPushButton { background-color: #444; color: #aaa; border: 1px solid #555; padding: 6px; border-radius: 4px; font-weight: bold; }")
        btn.toggled.connect(_update)
        _update(default_checked)
        return btn

    def _validate_premium(self):
        from PySide6.QtWidgets import QMessageBox
        import httpx
        
        key = self.premium_key_input.text().strip()
        model = self.premium_model_input.text().strip()
        
        if not key or not model:
            QMessageBox.warning(self, "Error", "Please enter both an API key and a model name.")
            return
            
        self.btn_validate_premium.setText("Validating...")
        self.btn_validate_premium.setEnabled(False)
        
        try:
            if "OpenAI" in getattr(self, 'premium_provider_combo', NoScrollComboBox()).currentText():
                url = "https://api.openai.com/v1/models"
                headers = {"Authorization": f"Bearer {key}"}
            else:
                QMessageBox.information(self, "Notice", "Format accepted. True validation will occur on first request.")
                self.btn_validate_premium.setText("Validate Premium Key & Model")
                self.btn_validate_premium.setEnabled(True)
                return

            r = httpx.get(url, headers=headers, timeout=5.0)
            if r.status_code == 200:
                QMessageBox.information(self, "Success", f"API Key is valid!\nModel: {model} is ready.")
            else:
                QMessageBox.warning(self, "Validation Failed", f"Invalid API Key. Code: {r.status_code}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to connect: {e}")
        finally:
            self.btn_validate_premium.setText("Validate Premium Key & Model")
            self.btn_validate_premium.setEnabled(True)

    def _validate_local(self, silent=False):
        from PySide6.QtWidgets import QMessageBox
        import httpx
        
        if not silent:
            self.btn_validate_local.setText("Fetching...")
            self.btn_validate_local.setEnabled(False)
            
        available_models = []
        try:
            r = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
            if r.status_code == 200:
                available_models = [m["name"] for m in r.json().get("models", [])]
                if not silent:
                    QMessageBox.information(self, "Success", f"Found {len(available_models)} local models!")
            elif not silent:
                QMessageBox.warning(self, "Error", f"Ollama returned status code: {r.status_code}")
        except Exception as e:
            if not silent:
                QMessageBox.warning(self, "Error", f"Could not connect to Ollama. Is it running?\n\n{e}")
                
        if available_models:
            self.ollama_chat_combo.clear()
            self.ollama_coding_combo.clear()
            self.ollama_chat_combo.addItems(available_models)
            self.ollama_coding_combo.addItem("(none - use Chat model)")
            self.ollama_coding_combo.addItems(available_models)
            
        if not silent:
            self.btn_validate_local.setText("Fetch & Validate Local Models")
            self.btn_validate_local.setEnabled(True)
    def _sync_active_model_combo(self):
        current_active = self.active_model_combo.currentText()
        self.active_model_combo.blockSignals(True)
        self.active_model_combo.clear()
        models = [le.text().strip() for le in self.model_inputs if le.text().strip()]
        self.active_model_combo.addItems(models)
        if current_active in models:
            self.active_model_combo.setCurrentText(current_active)
        elif models:
            self.active_model_combo.setCurrentText(models[0])
        self.active_model_combo.blockSignals(False)
        
    def validate_models(self):
        self.btn_validate.setEnabled(False)
        self.btn_validate.setText("Testing...")
        for lbl in self.model_status_labels:
            lbl.setText("⏳")
            
        key = self.key_input.text().strip()
        models = [le.text().strip() for le in self.model_inputs if le.text().strip()]
        
        self.validator = ValidatorThread(key, models, self.config.openrouter_base_url)
        self.validator.result_ready.connect(self.on_validation_result)
        self.validator.finished_validation.connect(self.on_validation_finished)
        self.validator.start()
        
    def on_validation_result(self, model_name, is_valid, err):
        for idx, le in enumerate(self.model_inputs):
            if le.text().strip() == model_name:
                self.model_status_labels[idx].setText("✅" if is_valid else "❌")
                self.model_status_labels[idx].setToolTip(err if not is_valid else "Working")
                
    def on_validation_finished(self):
        self.btn_validate.setEnabled(True)
        self.btn_validate.setText("Validate Key & Models")
        # Clear loading for empty fields
        for le, lbl in zip(self.model_inputs, self.model_status_labels):
            if not le.text().strip() and lbl.text() == "⏳":
                lbl.setText("")

    def showEvent(self, event):
        super().showEvent(event)
        # Apply stealth mode to this dialog if the parent window has it enabled
        if self.parent() and hasattr(self.parent(), '_stealth_active') and self.parent()._stealth_active:
            if hasattr(self.parent(), '_apply_privacy_flag'):
                self.parent()._apply_privacy_flag(stealth=True, target_hwnd=int(self.winId()))
                
    def setup_window_page(self):
        page = QWidget()
        main_layout = QVBoxLayout(page)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        
        inner = QWidget()
        inner.setAutoFillBackground(True)
        layout = QVBoxLayout(inner)
        
        # Heading Colors
        self.you_heading_color = getattr(self.config, 'ui_you_heading_color', '#E53935')
        self.interviewer_heading_color = getattr(self.config, 'ui_interviewer_heading_color', '#FF9900')
        self.voro_heading_color = getattr(self.config, 'ui_voro_heading_color', '#0055A4')
        
        layout.addWidget(_make_section_header("Heading Colors", self.theme))
        heading_hint = QLabel("Click a heading to change its color. The button shows a preview in the selected color.\n")
        heading_hint.setWordWrap(True)
        
        color_layout = QHBoxLayout()
        
        # YOU button
        self.btn_you_color = QPushButton(" YOU ")
        self.btn_you_color.setCursor(Qt.PointingHandCursor)
        self.btn_you_color.setFixedHeight(32)
        self.btn_you_color.setStyleSheet(self._heading_btn_style(self.you_heading_color))
        self.btn_you_color.clicked.connect(self.pick_you_color)
        color_layout.addWidget(self.btn_you_color)
        
        # INTERVIEWER button
        self.btn_interviewer_color = QPushButton(" INTERVIEWER ")
        self.btn_interviewer_color.setCursor(Qt.PointingHandCursor)
        self.btn_interviewer_color.setFixedHeight(32)
        self.btn_interviewer_color.setStyleSheet(self._heading_btn_style(self.interviewer_heading_color))
        self.btn_interviewer_color.clicked.connect(self.pick_interviewer_color)
        color_layout.addWidget(self.btn_interviewer_color)
        
        # VORO button
        self.btn_voro_color = QPushButton(" VORO ")
        self.btn_voro_color.setCursor(Qt.PointingHandCursor)
        self.btn_voro_color.setFixedHeight(32)
        self.btn_voro_color.setStyleSheet(self._heading_btn_style(self.voro_heading_color))
        self.btn_voro_color.clicked.connect(self.pick_voro_color)
        color_layout.addWidget(self.btn_voro_color)
        
        color_layout.addStretch()
        
        from PySide6.QtWidgets import QFrame
        colors_frame = QFrame()
        colors_frame.setObjectName("ColorBox")
        colors_frame.setStyleSheet(f"#ColorBox {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; }}")
        colors_layout = QVBoxLayout(colors_frame)
        colors_layout.setContentsMargins(15, 15, 15, 15)
        colors_layout.addWidget(heading_hint)
        colors_layout.addLayout(color_layout)
        
        layout.addWidget(colors_frame)
        
        layout.addSpacing(20)
        
        # Sliders
        from PySide6.QtWidgets import QFormLayout
        form_sliders = QFormLayout()
        form_sliders.setLabelAlignment(Qt.AlignLeft)
        form_sliders.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form_sliders.setVerticalSpacing(15)
        
        # Theme
        self.theme_combo = NoScrollComboBox()
        self.theme_combo.addItems(["system", "dark", "light"])
        self.theme_combo.setCurrentText(self.config.ui_theme_mode)
        self.theme_combo.setFixedWidth(180)
        form_sliders.addRow("Theme:", self.theme_combo)
        
        # Window Opacity
        self.opacity_slider = NoScrollSlider(Qt.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(self.config.ui_opacity)
        self.opacity_val_label = QLabel(str(self.opacity_slider.value()))
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_val_label.setText(str(v)))
        self.opacity_slider.setFixedWidth(180)
        w1 = QWidget()
        l1 = QHBoxLayout(w1)
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addWidget(self.opacity_slider)
        l1.addWidget(self.opacity_val_label)
        form_sliders.addRow("Window Opacity (%):", w1)
        
        
        # Font Size
        self.font_slider = NoScrollSlider(Qt.Horizontal)
        self.font_slider.setRange(10, 32)
        self.font_slider.setValue(self.config.ui_font_size)
        self.font_val_label = QLabel(str(self.font_slider.value()))
        self.font_slider.valueChanged.connect(lambda v: self.font_val_label.setText(str(v)))
        self.font_slider.setFixedWidth(180)
        w2 = QWidget()
        l2 = QHBoxLayout(w2)
        l2.setContentsMargins(0, 0, 0, 0)
        l2.addWidget(self.font_slider)
        l2.addWidget(self.font_val_label)
        form_sliders.addRow("Font Size (px):", w2)
        
        # Memory
        self.hist_slider = NoScrollSlider(Qt.Horizontal)
        self.hist_slider.setRange(1, 20)
        self.hist_slider.setValue(max(1, self.config.conversation_history_depth))
        self.hist_val_label = QLabel(str(self.hist_slider.value()))
        self.hist_slider.valueChanged.connect(lambda v: self.hist_val_label.setText(str(v)))
        self.hist_slider.setFixedWidth(180)
        w3 = QWidget()
        l3 = QHBoxLayout(w3)
        l3.setContentsMargins(0, 0, 0, 0)
        l3.addWidget(self.hist_slider)
        l3.addWidget(self.hist_val_label)
        form_sliders.addRow("Memory (past Q&A):", w3)
        
        from PySide6.QtWidgets import QFrame
        appearance_frame = QFrame()
        appearance_frame.setObjectName("AppearanceBox")
        appearance_frame.setStyleSheet(f"#AppearanceBox {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; }}")
        appearance_layout = QVBoxLayout(appearance_frame)
        appearance_layout.setContentsMargins(15, 15, 15, 15)
        appearance_layout.addLayout(form_sliders)
        
        layout.addWidget(_make_section_header("Appearance & Memory", self.theme))
        layout.addWidget(appearance_frame)
        
        
        # Checkboxes (Toggles)
        self.chk_pos = self._create_toggle_btn(self.config.ui_remember_position, "Remember Position Enabled", "Remember Position Disabled")
        layout.addWidget(self.chk_pos)
        
        layout.addSpacing(10)
        layout.addWidget(_make_section_header("AI Engine Personality & Tone", self.theme))
        
        from PySide6.QtWidgets import QFrame
        ai_frame = QFrame()
        ai_frame.setObjectName("AIToneBox")
        ai_frame.setStyleSheet(f"#AIToneBox {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; }}")
        ai_layout = QVBoxLayout(ai_frame)
        ai_layout.setContentsMargins(15, 15, 15, 15)
        
        from PySide6.QtWidgets import QFormLayout
        form_ai = QFormLayout()
        form_ai.setLabelAlignment(Qt.AlignLeft)
        form_ai.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        self.ai_tone_combo = NoScrollComboBox()
        self.ai_tone_combo.addItems(["Conversational (Script)", "Conversational (Hinglish)", "Direct & Technical", "Supportive & Encouraging"])
        self.ai_tone_combo.setCurrentText(getattr(self.config, 'ai_tone', 'Conversational (Script)'))
        self.ai_tone_combo.setFixedWidth(180)
        
        form_ai.addRow("AI Tone:", self.ai_tone_combo)
        ai_layout.addLayout(form_ai)
        
        layout.addWidget(ai_frame)
        
        layout.addSpacing(10)
        layout.addWidget(_make_section_header("Speech-to-Text (STT) Options", self.theme))
        
        from PySide6.QtWidgets import QFrame
        stt_frame = QFrame()
        stt_frame.setObjectName("STTBox")
        stt_frame.setStyleSheet(f"#STTBox {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; }}")
        stt_layout = QVBoxLayout(stt_frame)
        stt_layout.setContentsMargins(15, 15, 15, 15)
        
        from PySide6.QtWidgets import QFormLayout
        form_stt = QFormLayout()
        form_stt.setLabelAlignment(Qt.AlignLeft)
        form_stt.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form_stt.setVerticalSpacing(15)
        
        # Compute device hardcoded to CPU for Norvi Agency distribution
        self.stt_device_combo = NoScrollComboBox()
        self.stt_device_combo.addItems(["cpu"])
        self.stt_device_combo.setCurrentText("cpu")
        self.stt_device_combo.setFixedWidth(180)
        # Hidden - not shown to user
        
        self.groq_api_input = QLineEdit()
        self.groq_api_input.setText(getattr(self.config, 'groq_api_key', ''))
        self.groq_api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.groq_api_input.setPlaceholderText("Enter Groq API Key for lightning-fast voice speed")
        form_stt.addRow("Groq API Key (For Fast Speed):", self.groq_api_input)

        self.stt_model_combo = NoScrollComboBox()
        self.stt_model_combo.addItems(["small.en", "small", "medium.en", "medium"])
        saved_size = getattr(self.config, 'stt_model_size', 'small.en')
        if saved_size == 'base.en': saved_size = 'small.en'
        if saved_size == 'base': saved_size = 'small'
        self.stt_model_combo.setCurrentText(saved_size)
        self.stt_model_combo.setFixedWidth(180)
        form_stt.addRow("STT Model Size (Local Fallback):", self.stt_model_combo)
        
        self.stt_dir_input = QLineEdit()
        self.stt_dir_input.setText(getattr(self.config, 'stt_model_dir', ''))
        self.stt_dir_input.setPlaceholderText("Directory where models are downloaded...")
        
        stt_dir_box = QWidget()
        stt_dir_l = QHBoxLayout(stt_dir_box)
        stt_dir_l.setContentsMargins(0, 0, 0, 0)
        stt_dir_l.addWidget(self.stt_dir_input)
        self.btn_stt_dir_browse = QPushButton("Browse")
        self.btn_stt_dir_browse.clicked.connect(self._browse_stt_dir)
        stt_dir_l.addWidget(self.btn_stt_dir_browse)
        
        form_stt.addRow("STT Models Directory:", stt_dir_box)
        
        stt_layout.addLayout(form_stt)
        
        stt_layout.addWidget(QLabel("STT Context Prompt (Helps with heavy accents/jargon):"))
        from PySide6.QtWidgets import QTextEdit
        self.stt_context_input = QTextEdit()
        self.stt_context_input.setMaximumHeight(80)
        self.stt_context_input.setPlainText(getattr(self.config, 'stt_context_prompt', ''))
        stt_layout.addWidget(self.stt_context_input)
        
        layout.addWidget(stt_frame)
        layout.addSpacing(20)
        layout.addWidget(_make_section_header("Offline Model Downloads", self.theme))
        
        from PySide6.QtWidgets import QFrame, QProgressBar
        dl_frame = QFrame()
        dl_frame.setObjectName("DLBox")
        dl_frame.setStyleSheet(f"#DLBox {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; }}")
        dl_layout = QVBoxLayout(dl_frame)
        dl_layout.setContentsMargins(15, 15, 15, 15)
        
        form_dl = QFormLayout()
        form_dl.setLabelAlignment(Qt.AlignLeft)
        form_dl.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form_dl.setVerticalSpacing(15)
        
        self.dl_dir_input = QLineEdit()
        saved_dir = getattr(self.config, 'stt_model_dir', '')
        self.dl_dir_input.setText(saved_dir)
        self.dl_dir_input.setPlaceholderText("Default (C:\\Users\\...\\.cache\\huggingface\\hub)")
        
        dir_box = QWidget()
        dir_l = QHBoxLayout(dir_box)
        dir_l.setContentsMargins(0, 0, 0, 0)
        dir_l.addWidget(self.dl_dir_input)
        self.btn_dl_browse = QPushButton("Browse")
        self.btn_dl_browse.clicked.connect(self._browse_dl_dir)
        dir_l.addWidget(self.btn_dl_browse)
        form_dl.addRow("Model Save Directory:", dir_box)
        
        self.dl_model_combo = NoScrollComboBox()
        self.dl_model_combo.addItems(["small.en", "small", "medium.en", "medium"])
        self.dl_model_combo.setFixedWidth(180)
        
        model_box = QWidget()
        model_l = QHBoxLayout(model_box)
        model_l.setContentsMargins(0, 0, 0, 0)
        model_l.addWidget(self.dl_model_combo)
        
        self.btn_dl_start = QPushButton("Download")
        self.btn_dl_start.setProperty("class", "primary")
        self.btn_dl_start.clicked.connect(self._start_model_dl)
        model_l.addWidget(self.btn_dl_start)
        
        self.btn_dl_pause = QPushButton("Pause")
        self.btn_dl_pause.setEnabled(False)
        self.btn_dl_pause.clicked.connect(self._pause_model_dl)
        model_l.addWidget(self.btn_dl_pause)
        
        self.btn_dl_cancel = QPushButton("Cancel")
        self.btn_dl_cancel.setEnabled(False)
        self.btn_dl_cancel.clicked.connect(self._cancel_model_dl)
        model_l.addWidget(self.btn_dl_cancel)
        
        form_dl.addRow("Download STT Model:", model_box)
        
        self.dl_status_lbl = QLabel("Ready")
        self.dl_status_lbl.setStyleSheet("font-weight: bold; color: #4CAF50;")
        form_dl.addRow("Status:", self.dl_status_lbl)
        
        dl_layout.addLayout(form_dl)
        layout.addWidget(dl_frame)


        layout.addSpacing(20)
        layout.addWidget(_make_section_header("Interface Shortcuts", self.theme))
        
        from PySide6.QtWidgets import QFormLayout, QFrame
        hk_frame = QFrame()
        hk_frame.setObjectName("HKBox")
        hk_frame.setStyleSheet(f"#HKBox {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; }}")
        hk_layout = QVBoxLayout(hk_frame)
        hk_layout.setContentsMargins(15, 15, 15, 15)
        
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setVerticalSpacing(15)
        
        self.hotkey_input = self._create_hk_input(self.config.ui_global_hotkey)
        form.addRow("Global Summon Hotkey:", self.hotkey_input)
        
        self.stop_hotkey_input = self._create_hk_input(getattr(self.config, 'ui_stop_hotkey', 'ctrl+shift+c'))
        form.addRow("Stop Current Task Hotkey:", self.stop_hotkey_input)
        
        self.taskbar_hotkey_input = self._create_hk_input(getattr(self.config, 'ui_taskbar_hotkey', 'ctrl+shift+t'))
        form.addRow("Toggle Taskbar Hotkey:", self.taskbar_hotkey_input)
        
        self.maximize_hotkey_input = self._create_hk_input(getattr(self.config, 'ui_maximize_hotkey', 'F11'))
        form.addRow("Maximize Window Hotkey:", self.maximize_hotkey_input)
        
        self.clear_session_hotkey_input = self._create_hk_input(getattr(self.config, 'ui_clear_session_hotkey', 'ctrl+shift+backspace'))
        form.addRow("Clear Session Hotkey:", self.clear_session_hotkey_input)
        
        self.toggle_tray_hotkey_input = self._create_hk_input(getattr(self.config, 'ui_toggle_tray_hotkey', 'ctrl+shift+y'))
        form.addRow("Toggle Tray Icon Hotkey:", self.toggle_tray_hotkey_input)
        
        self.stealth_hotkey_input = self._create_hk_input(getattr(self.config, 'ui_stealth_hotkey', 'ctrl+shift+g'))
        form.addRow("Stealth Mode Hotkey:", self.stealth_hotkey_input)
        
        hk_layout.addLayout(form)
        layout.addWidget(hk_frame)
        
        # --- Stealth Mode Toggle ---
        from app.utils.logging import logger as _logger
        stealth_header = _make_section_header("Stealth Mode", self.theme)
        layout.addWidget(stealth_header)
        
        stealth_hint = QLabel("When Stealth Mode is ON, Voro is completely invisible to screen recording,\nscreenshots, and screenshares. Toggle with the hotkey above or the button below.")
        stealth_hint.setWordWrap(True)
        stealth_hint.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        layout.addWidget(stealth_hint)
        
        stealth_val = getattr(self.config, 'ui_stealth_mode', False)
        self.stealth_toggle_btn = self._create_toggle_btn(stealth_val, "Stealth Mode: ON", "Stealth Mode: OFF")
        layout.addWidget(self.stealth_toggle_btn)


        layout.addStretch()
        scroll.setWidget(inner)
        main_layout.addWidget(scroll)
        self.pages.addWidget(page)
        
    def setup_vision_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        
        inner = QWidget()
        inner.setAutoFillBackground(True)
        inner_layout = QVBoxLayout(inner)
        
        inner_layout.addWidget(_make_section_header("Vision Capture Source", self.theme))
        
        self.chk_vision_enabled = self._create_toggle_btn(getattr(self.config, 'ui_vision_enabled', True), "Vision System Enabled", "Vision System Disabled")
        inner_layout.addWidget(self.chk_vision_enabled)
        
        from PySide6.QtWidgets import QFrame
        vision_frame = QFrame()
        vision_frame.setObjectName("VisionBox")
        vision_frame.setStyleSheet(f"#VisionBox {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; }}")
        vision_layout = QVBoxLayout(vision_frame)
        vision_layout.setContentsMargins(15, 15, 15, 15)
        
        from PySide6.QtWidgets import QFormLayout
        form_vis = QFormLayout()
        form_vis.setLabelAlignment(Qt.AlignLeft)
        form_vis.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form_vis.setVerticalSpacing(15)
        
        self.capture_mode_combo = NoScrollComboBox()
        self.capture_mode_combo.addItems(["Monitor", "Window"])
        saved_mode = getattr(self.config, 'ui_capture_mode', 'monitor').capitalize()
        self.capture_mode_combo.setCurrentText(saved_mode)
        self.capture_mode_combo.setFixedWidth(180)
        form_vis.addRow("Capture Mode:", self.capture_mode_combo)
        
        self.capture_target_combo = NoScrollComboBox()
        self.capture_target_combo.setMinimumWidth(350)
        form_vis.addRow("Capture Target:", self.capture_target_combo)
        
        self.preview_label = QLabel()
        self.preview_label.setFixedSize(350, 197)
        self.preview_label.setStyleSheet("background-color: #000; border: 1px solid #444;")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setText("Loading preview...")
        form_vis.addRow("Preview:", self.preview_label)
        
        vision_layout.addLayout(form_vis)
        
        inner_layout.addWidget(vision_frame)
        
        self.capture_target_combo.currentIndexChanged.connect(self._update_preview)
        self.capture_mode_combo.currentTextChanged.connect(self._update_capture_targets)
        self.chk_vision_enabled.toggled.connect(self._on_vision_toggled)
        self._update_capture_targets(self.capture_mode_combo.currentText())
        self._on_vision_toggled(self.chk_vision_enabled.isChecked())
        
        saved_target = getattr(self.config, 'ui_capture_target', '1')
        def set_target():
            idx = -1
            if saved_mode == "Monitor":
                idx = self.capture_target_combo.findText(f"Monitor {saved_target}", Qt.MatchStartsWith)
            else:
                idx = self.capture_target_combo.findText(saved_target)
            if idx >= 0:
                self.capture_target_combo.setCurrentIndex(idx)
        
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, set_target)
        
        inner_layout.addSpacing(20)
        inner_layout.addWidget(_make_section_header("Auto-Monitor", self.theme))
        
        self.chk_auto_monitor = self._create_toggle_btn(getattr(self.config, 'enable_auto_monitor', False), "Auto-Monitor Enabled", "Auto-Monitor Disabled")
        inner_layout.addWidget(self.chk_auto_monitor)
        
        inner_layout.addSpacing(20)
        inner_layout.addWidget(_make_section_header("Optical Character Recognition (OCR)", self.theme))
        
        from PySide6.QtWidgets import QFrame, QFormLayout
        ocr_frame = QFrame()
        ocr_frame.setObjectName("OCRBox")
        ocr_frame.setStyleSheet(f"#OCRBox {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; }}")
        ocr_layout = QVBoxLayout(ocr_frame)
        ocr_layout.setContentsMargins(15, 15, 15, 15)
        
        form_ocr = QFormLayout()
        form_ocr.setLabelAlignment(Qt.AlignLeft)
        form_ocr.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form_ocr.setVerticalSpacing(15)
        
        self.ocr_device_combo = NoScrollComboBox()
        self.ocr_device_combo.addItems(["cuda", "cpu"])
        self.ocr_device_combo.setCurrentText(getattr(self.config, 'ocr_compute_device', 'cuda'))
        self.ocr_device_combo.setFixedWidth(180)
        form_ocr.addRow("Compute Device:", self.ocr_device_combo)
        
        tess_val = getattr(self.config, 'tesseract_cmd_path', '')
        if not tess_val: tess_val = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        self.tess_path_input = QLineEdit(tess_val)
        
        tess_box = QWidget()
        tess_l = QHBoxLayout(tess_box)
        tess_l.setContentsMargins(0, 0, 0, 0)
        tess_l.addWidget(self.tess_path_input)
        self.btn_tess_browse = QPushButton("Browse")
        self.btn_tess_browse.clicked.connect(self.browse_tesseract_path)
        tess_l.addWidget(self.btn_tess_browse)
        
        form_ocr.addRow("Tesseract Path:", tess_box)
        ocr_layout.addLayout(form_ocr)
        inner_layout.addWidget(ocr_frame)
        
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self.pages.addWidget(page)
        
    def setup_audio_page(self):
        from PySide6.QtCore import Qt
        page = QWidget()
        layout = QVBoxLayout(page)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        
        inner = QWidget()
        inner.setAutoFillBackground(True)
        inner_layout = QVBoxLayout(inner)
        
        from PySide6.QtWidgets import QFrame
        
        # 1. User Audio Capture
        inner_layout.addWidget(_make_section_header("1. User Audio Capture (Microphone)", self.theme))
        
        user_frame = QFrame()
        user_frame.setObjectName("AudioBox")
        user_frame.setStyleSheet(f"#AudioBox {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; }}")
        user_layout = QVBoxLayout(user_frame)
        user_layout.setContentsMargins(15, 15, 15, 15)
        
        self.btn_mute_mic = QPushButton()
        self.btn_mute_mic.setCheckable(True)
        self.btn_mute_mic.setChecked(getattr(self.config, 'mute_user_mic', False))
        self.btn_mute_mic.setCursor(Qt.PointingHandCursor)
        user_layout.addWidget(self.btn_mute_mic)
        
        from PySide6.QtWidgets import QFormLayout
        form_ua = QFormLayout()
        form_ua.setLabelAlignment(Qt.AlignLeft)
        form_ua.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        self.user_device_combo = NoScrollComboBox()
        self.user_device_combo.addItem("Default Windows Input")
        try:
            import sounddevice as sd
            for d in sd.query_devices():
                if d['max_input_channels'] > 0:
                    self.user_device_combo.addItem(d['name'])
        except Exception:
            pass
        saved_user_mic = getattr(self.config, 'user_audio_device', 'Default Windows Input')
        self.user_device_combo.setCurrentText(saved_user_mic)
        self.user_device_combo.setMinimumWidth(250)
        form_ua.addRow("Input Device:", self.user_device_combo)
        user_layout.addLayout(form_ua)
        
        from PySide6.QtWidgets import QFormLayout
        form_mic = QFormLayout()
        form_mic.setLabelAlignment(Qt.AlignLeft)
        form_mic.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.mute_mic_hotkey_input = self._create_hk_input(getattr(self.config, 'ui_mute_mic_hotkey', 'ctrl+shift+m'))
        form_mic.addRow("Mute Toggle Hotkey:", self.mute_mic_hotkey_input)
        user_layout.addLayout(form_mic)
        
        def _toggle_mic(checked):
            self.user_device_combo.setEnabled(not checked)
            if checked:
                self.btn_mute_mic.setText("User Mic Disabled")
                self.btn_mute_mic.setStyleSheet("QPushButton { background-color: #444; color: #aaa; border: 1px solid #555; padding: 6px; border-radius: 4px; font-weight: bold; }")
            else:
                self.btn_mute_mic.setText("User Mic Enabled")
                self.btn_mute_mic.setStyleSheet("QPushButton { background-color: #0078D7; color: white; border: none; padding: 6px; border-radius: 4px; font-weight: bold; }")
        self.btn_mute_mic.toggled.connect(_toggle_mic)
        _toggle_mic(self.btn_mute_mic.isChecked())
        
        inner_layout.addWidget(user_frame)
        
        # 2. Interviewer Audio Capture
        inner_layout.addWidget(_make_section_header("2. Interviewer Audio Capture (System Audio)", self.theme))
        
        sys_frame = QFrame()
        sys_frame.setObjectName("AudioBox")
        sys_frame.setStyleSheet(f"#AudioBox {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; }}")
        sys_layout = QVBoxLayout(sys_frame)
        sys_layout.setContentsMargins(15, 15, 15, 15)
        
        self.btn_mute_sys = QPushButton()
        self.btn_mute_sys.setCheckable(True)
        self.btn_mute_sys.setChecked(getattr(self.config, 'mute_system_audio', False))
        self.btn_mute_sys.setCursor(Qt.PointingHandCursor)
        sys_layout.addWidget(self.btn_mute_sys)
        
        from PySide6.QtWidgets import QFormLayout
        form_sa = QFormLayout()
        form_sa.setLabelAlignment(Qt.AlignLeft)
        form_sa.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        self.sys_device_combo = NoScrollComboBox()
        self.sys_device_combo.addItem("Default Windows Output")
        try:
            import soundcard as sc
            for s in sc.all_speakers():
                self.sys_device_combo.addItem(s.name)
        except Exception:
            pass
        saved_sys_spk = getattr(self.config, 'system_audio_device', 'Default Windows Output')
        self.sys_device_combo.setCurrentText(saved_sys_spk)
        self.sys_device_combo.setMinimumWidth(250)
        form_sa.addRow("Speaker Device:", self.sys_device_combo)
        sys_layout.addLayout(form_sa)
        
        from PySide6.QtWidgets import QFormLayout
        form_sys = QFormLayout()
        form_sys.setLabelAlignment(Qt.AlignLeft)
        form_sys.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.mute_sys_hotkey_input = self._create_hk_input(getattr(self.config, 'ui_mute_sys_hotkey', 'ctrl+shift+a'))
        form_sys.addRow("Mute Toggle Hotkey:", self.mute_sys_hotkey_input)
        sys_layout.addLayout(form_sys)
        
        def _toggle_sys(checked):
            self.sys_device_combo.setEnabled(not checked)
            if checked:
                self.btn_mute_sys.setText("System Audio Disabled")
                self.btn_mute_sys.setStyleSheet("QPushButton { background-color: #444; color: #aaa; border: 1px solid #555; padding: 6px; border-radius: 4px; font-weight: bold; }")
            else:
                self.btn_mute_sys.setText("System Audio Enabled")
                self.btn_mute_sys.setStyleSheet("QPushButton { background-color: #0078D7; color: white; border: none; padding: 6px; border-radius: 4px; font-weight: bold; }")
        self.btn_mute_sys.toggled.connect(_toggle_sys)
        _toggle_sys(self.btn_mute_sys.isChecked())
        
        inner_layout.addWidget(sys_frame)
        
        # 3. Voice Output
        inner_layout.addWidget(_make_section_header("3. Voice Output (Voro TTS)", self.theme))
        
        tts_frame = QFrame()
        tts_frame.setObjectName("AudioBox")
        tts_frame.setStyleSheet(f"#AudioBox {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; }}")
        tts_layout = QVBoxLayout(tts_frame)
        tts_layout.setContentsMargins(15, 15, 15, 15)
        
        self.btn_tts_muted = QPushButton()
        self.btn_tts_muted.setCheckable(True)
        self.btn_tts_muted.setChecked(getattr(self.config, 'ui_tts_muted', False))
        self.btn_tts_muted.setCursor(Qt.PointingHandCursor)
        tts_layout.addWidget(self.btn_tts_muted)
        
        from PySide6.QtWidgets import QSlider
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QFormLayout
        form_tts_vol = QFormLayout()
        form_tts_vol.setLabelAlignment(Qt.AlignLeft)
        form_tts_vol.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        self.tts_vol_slider = NoScrollSlider(Qt.Horizontal)
        self.tts_vol_slider.setRange(0, 100)
        self.tts_vol_slider.setValue(getattr(self.config, 'ui_tts_volume', 100))
        self.tts_vol_slider.setFixedWidth(180)
        self.tts_vol_label = QLabel(str(self.tts_vol_slider.value()))
        self.tts_vol_slider.valueChanged.connect(lambda v: self.tts_vol_label.setText(str(v)))
        
        w_vol = QWidget()
        l_vol = QHBoxLayout(w_vol)
        l_vol.setContentsMargins(0, 0, 0, 0)
        l_vol.addWidget(self.tts_vol_slider)
        l_vol.addWidget(self.tts_vol_label)
        
        form_tts_vol.addRow("Voice Volume (0-100):", w_vol)

        self.tts_speed_combo = NoScrollComboBox()
        self.tts_speed_combo.addItems([
            "-50%", "-40%", "-30%", "-20%", "-10%",
            "+0%",
            "+10%", "+20%", "+30%", "+40%", "+50%"
        ])
        current_speed = getattr(self.config, 'ui_tts_rate', '+0%')
        idx = self.tts_speed_combo.findText(current_speed, Qt.MatchContains)
        if idx >= 0: self.tts_speed_combo.setCurrentIndex(idx)
        self.tts_speed_combo.setMinimumWidth(250)
        form_tts_vol.addRow("Speech Speed:", self.tts_speed_combo)

        from PySide6.QtMultimedia import QMediaDevices
        self.tts_output_device_combo = NoScrollComboBox()
        out_devices = QMediaDevices.audioOutputs()
        out_device_names = ["Default System Device"]
        for d in out_devices:
            desc = d.description()
            if desc not in out_device_names:
                out_device_names.append(desc)
        self.tts_output_device_combo.addItems(out_device_names)
        current_out_dev = getattr(self.config, 'ui_tts_output_device', 'Default System Device')
        idx = self.tts_output_device_combo.findText(current_out_dev, Qt.MatchContains)
        if idx >= 0: self.tts_output_device_combo.setCurrentIndex(idx)
        self.tts_output_device_combo.setMinimumWidth(250)
        form_tts_vol.addRow("Output Audio Device:", self.tts_output_device_combo)

        tts_layout.addLayout(form_tts_vol)
        
        from PySide6.QtWidgets import QFormLayout
        form_voice = QFormLayout()
        form_voice.setLabelAlignment(Qt.AlignLeft)
        form_voice.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        self.voice_combo = NoScrollComboBox()
        self.voice_combo.addItems([
            "en-US-AriaNeural (Female)",
            "en-US-GuyNeural (Male)",
            "en-US-JennyNeural (Female)",
            "en-US-ChristopherNeural (Male)",
            "en-GB-SoniaNeural (Female)",
            "en-GB-RyanNeural (Male)",
            "en-AU-NatashaNeural (Female)",
            "en-AU-WilliamNeural (Male)",
            "hi-IN-SwaraNeural (Female - Hinglish)",
            "hi-IN-MadhurNeural (Male - Hinglish)",
        ])
        current_voice = getattr(self.config, 'ui_voice', 'en-US-AriaNeural')
        idx = self.voice_combo.findText(current_voice, Qt.MatchContains)
        if idx >= 0: self.voice_combo.setCurrentIndex(idx)
        self.voice_combo.setMinimumWidth(250)
        
        self.btn_test_voice = QPushButton("Test Voice")
        self.btn_test_voice.clicked.connect(self._test_voice)
        
        v_box = QWidget()
        v_l = QHBoxLayout(v_box)
        v_l.setContentsMargins(0, 0, 0, 0)
        v_l.addWidget(self.voice_combo)
        v_l.addWidget(self.btn_test_voice)
        
        form_voice.addRow("Voice Selection:", v_box)
        tts_layout.addLayout(form_voice)
        
        from PySide6.QtWidgets import QFormLayout
        form_tts = QFormLayout()
        form_tts.setLabelAlignment(Qt.AlignLeft)
        form_tts.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.tts_mute_hotkey_input = self._create_hk_input(getattr(self.config, 'ui_tts_mute_hotkey', 'ctrl+shift+x'))
        form_tts.addRow("Mute Toggle Hotkey:", self.tts_mute_hotkey_input)
        tts_layout.addLayout(form_tts)
        
        def _toggle_tts(checked):
            self.tts_vol_slider.setEnabled(not checked)
            if hasattr(self, 'tts_speed_combo'):
                self.tts_speed_combo.setEnabled(not checked)
            if hasattr(self, 'tts_output_device_combo'):
                self.tts_output_device_combo.setEnabled(not checked)
            self.voice_combo.setEnabled(not checked)
            self.btn_test_voice.setEnabled(not checked)
            if checked:
                self.btn_tts_muted.setText("Voro Voice (TTS) Disabled")
                self.btn_tts_muted.setStyleSheet("QPushButton { background-color: #444; color: #aaa; border: 1px solid #555; padding: 6px; border-radius: 4px; font-weight: bold; }")
            else:
                self.btn_tts_muted.setText("Voro Voice (TTS) Enabled")
                self.btn_tts_muted.setStyleSheet("QPushButton { background-color: #0078D7; color: white; border: none; padding: 6px; border-radius: 4px; font-weight: bold; }")
            
        self.btn_tts_muted.toggled.connect(_toggle_tts)
        _toggle_tts(self.btn_tts_muted.isChecked())
        
        inner_layout.addWidget(tts_frame)
        
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self.pages.addWidget(page)

    def _test_voice(self):
        voice_id = self.voice_combo.currentText().split(" ")[0]
        self.btn_test_voice.setText("Playing...")
        self.btn_test_voice.setEnabled(False)
        def _reset():
            self.btn_test_voice.setText("Test Voice")
            self.btn_test_voice.setEnabled(True)
        # Play using QMediaPlayer
        import threading
        def fetch_audio():
            import edge_tts, asyncio, tempfile
            async def run():
                communicate = edge_tts.Communicate("Hello, I am Voro. This is how I sound.", voice_id)
                tmp = tempfile.mktemp(suffix=".mp3")
                await communicate.save(tmp)
                return tmp
            return asyncio.run(run())
            
        def on_fetched(filepath):
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PySide6.QtCore import QUrl
            if not hasattr(self, '_test_player'):
                self._test_player = QMediaPlayer()
                self._test_audio = QAudioOutput()
                self._test_player.setAudioOutput(self._test_audio)
                self._test_player.mediaStatusChanged.connect(self._on_test_status)
            self._test_player.setSource(QUrl.fromLocalFile(filepath))
            self._test_player.play()
            
        def thread_task():
            try:
                fp = fetch_audio()
                from PySide6.QtCore import QMetaObject, Qt, Q_ARG
                QMetaObject.invokeMethod(self, "_play_test_audio", Qt.QueuedConnection, Q_ARG(str, fp))
            except Exception as e:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, _reset)
                
        self._test_reset_fn = _reset
        threading.Thread(target=thread_task, daemon=True).start()
        

    @Slot(str)
    def _play_test_audio(self, filepath):
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
        from PySide6.QtCore import QUrl
        if not hasattr(self, '_test_player'):
            self._test_player = QMediaPlayer()
            self._test_audio = QAudioOutput()
            self._test_player.setAudioOutput(self._test_audio)
            self._test_player.mediaStatusChanged.connect(self._on_test_status)
        self._test_player.setSource(QUrl.fromLocalFile(filepath))
        self._test_player.play()

    def _on_test_status(self, status):
        from PySide6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if hasattr(self, '_test_reset_fn'):
                self._test_reset_fn()



    def setup_profile_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        
        inner = QWidget()
        inner.setAutoFillBackground(True)
        inner_layout = QVBoxLayout(inner)
        
        # Profile Selector
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Profile:"))
        self.profile_combo = NoScrollComboBox()
        self.profile_combo.addItems(list(self.context_manager.profiles.keys()))
        self.profile_combo.setCurrentText(self.context_manager.active_profile_name)
        self.profile_combo.currentTextChanged.connect(self.on_profile_changed)
        top_layout.addWidget(self.profile_combo)
        
        btn_new_profile = QPushButton("New")
        btn_new_profile.clicked.connect(self.new_profile)
        btn_del_profile = QPushButton("Delete")
        btn_del_profile.clicked.connect(self.delete_profile)
        top_layout.addWidget(btn_new_profile)
        top_layout.addWidget(btn_del_profile)
        inner_layout.addLayout(top_layout)
        
        inner_layout.addWidget(_make_section_header("Personal Knowledge", self.theme))        
        from PySide6.QtWidgets import QFrame, QFormLayout
        prof_frame = QFrame()
        prof_frame.setObjectName("ProfBox")
        prof_frame.setStyleSheet(f"#ProfBox {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; }}")
        prof_layout = QVBoxLayout(prof_frame)
        prof_layout.setContentsMargins(15, 15, 15, 15)
        
        form_prof = QFormLayout()
        form_prof.setLabelAlignment(Qt.AlignLeft)
        form_prof.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form_prof.setVerticalSpacing(15)
        
        self.profile_name = QLineEdit()
        form_prof.addRow("Name:", self.profile_name)
        
        self.profile_education = QLineEdit()
        form_prof.addRow("Education:", self.profile_education)
        
        self.profile_skills = QLineEdit()
        form_prof.addRow("Skills (comma separated):", self.profile_skills)
        
        self.profile_projects = QTextEdit()
        self.profile_projects.setMaximumHeight(80)
        form_prof.addRow("Projects / Experience:", self.profile_projects)
        
        # PDF Resume Upload
        self.lbl_resume_status = QLabel(" ⚪ Resume: Not Uploaded ")
        self.lbl_resume_status.setStyleSheet(
            "color: #666; background-color: rgba(128,128,128,0.15); "
            "padding: 3px 10px; border-radius: 8px;"
        )
        
        res_box = QWidget()
        res_l = QHBoxLayout(res_box)
        res_l.setContentsMargins(0, 0, 0, 0)
        res_l.addWidget(self.lbl_resume_status)
        btn_upload = QPushButton("Upload PDF")
        btn_upload.clicked.connect(self.upload_pdf_resume)
        res_l.addWidget(btn_upload)
        
        form_prof.addRow("Resume (PDF):", res_box)
        prof_layout.addLayout(form_prof)
        inner_layout.addWidget(prof_frame)
        
        # We store the extracted text here invisibly
        self._extracted_resume_text = ""
        
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self.pages.addWidget(page)
        
    def setup_company_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        
        inner = QWidget()
        inner.setAutoFillBackground(True)
        inner_layout = QVBoxLayout(inner)
        
        inner_layout.addWidget(_make_section_header("Company & Interview Details", self.theme))
        inner_layout.addWidget(QLabel("Note: These details are attached to your currently selected Profile."))        
        from PySide6.QtWidgets import QFrame, QFormLayout
        comp_frame = QFrame()
        comp_frame.setObjectName("CompBox")
        comp_frame.setStyleSheet(f"#CompBox {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; }}")
        comp_layout = QVBoxLayout(comp_frame)
        comp_layout.setContentsMargins(15, 15, 15, 15)
        
        form_comp = QFormLayout()
        form_comp.setLabelAlignment(Qt.AlignLeft)
        form_comp.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form_comp.setVerticalSpacing(15)
        
        self.comp_name = QLineEdit()
        form_comp.addRow("Company Name:", self.comp_name)
        
        self.comp_role = QLineEdit()
        form_comp.addRow("Role Applying For:", self.comp_role)
        
        self.comp_details = QTextEdit()
        self.comp_details.setMaximumHeight(80)
        form_comp.addRow("Company Details:", self.comp_details)
        
        self.comp_info = QTextEdit()
        self.comp_info.setMaximumHeight(80)
        form_comp.addRow("Important Info:", self.comp_info)
        
        comp_layout.addLayout(form_comp)
        inner_layout.addWidget(comp_frame)
        
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self.pages.addWidget(page)
        
    def load_profile_fields(self, profile_name):
        if profile_name not in self.context_manager.profiles: return
        ctx = self.context_manager.profiles[profile_name]
        self.profile_name.setText(ctx.personal.name)
        self.profile_education.setText(ctx.personal.education)
        self.profile_skills.setText(", ".join(ctx.personal.skills))
        self.profile_projects.setPlainText(ctx.personal.projects)
        
        self._extracted_resume_text = ctx.personal.resume_text
        if self._extracted_resume_text:
            self.lbl_resume_status.setText(f" ✔ Resume: Loaded ({len(self._extracted_resume_text)} characters) ")
            self.lbl_resume_status.setStyleSheet(
                "color: #003300; background-color: #00C853; font-weight: bold; "
                "padding: 3px 10px; border-radius: 8px;"
            )
        else:
            self.lbl_resume_status.setText(" ✗ Resume: Not Uploaded ")
            self.lbl_resume_status.setStyleSheet(
                "color: #666; background-color: rgba(128,128,128,0.15); "
                "padding: 3px 10px; border-radius: 8px;"
            )
            
        self.comp_name.setText(ctx.interview.company)
        self.comp_role.setText(ctx.interview.role)
        self.comp_details.setPlainText(ctx.interview.company_details)
        self.comp_info.setPlainText(ctx.interview.important_info)
        

    def _save_settings_geometry(self):
        from dotenv import set_key
        geo = self.geometry()
        set_key(self.env_path, "UI_SETTINGS_WIN_X", str(geo.x()))
        set_key(self.env_path, "UI_SETTINGS_WIN_Y", str(geo.y()))
        set_key(self.env_path, "UI_SETTINGS_WIN_W", str(geo.width()))
        set_key(self.env_path, "UI_SETTINGS_WIN_H", str(geo.height()))

    def closeEvent(self, event):
        self._save_settings_geometry()
        super().closeEvent(event)

    def accept(self):
        self._save_settings_geometry()
        super().accept()

    def reject(self):
        self._save_settings_geometry()
        super().reject()

    def save_current_profile_fields(self):
        if not hasattr(self, '_last_selected_profile') or not self._last_selected_profile: return
        if self._last_selected_profile not in self.context_manager.profiles: return
        skills_list = [s.strip() for s in self.profile_skills.text().split(",") if s.strip()]
        ctx = self.context_manager.profiles[self._last_selected_profile]
        ctx.personal.name = self.profile_name.text().strip()
        ctx.personal.education = self.profile_education.text().strip()
        ctx.personal.skills = skills_list
        ctx.personal.projects = self.profile_projects.toPlainText().strip()
        ctx.personal.resume_text = self._extracted_resume_text
        ctx.interview.company = self.comp_name.text().strip()
        ctx.interview.role = self.comp_role.text().strip()
        ctx.interview.company_details = self.comp_details.toPlainText().strip()
        ctx.interview.important_info = self.comp_info.toPlainText().strip()
        
        self.context_manager.save()

    def on_profile_changed(self, new_profile):
        if not new_profile: return
        self.save_current_profile_fields()
        self.load_profile_fields(new_profile)
        self._last_selected_profile = new_profile
        self.context_manager.switch_profile(new_profile)
        
    def new_profile(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Profile", "Profile Name:")
        if ok and name and name not in self.context_manager.profiles:
            self.save_current_profile_fields()
            self.context_manager.create_profile(name)
            self.profile_combo.blockSignals(True)
            self.profile_combo.addItem(name)
            self.profile_combo.setCurrentText(name)
            self.profile_combo.blockSignals(False)
            self.load_profile_fields(name)
            self._last_selected_profile = name
            
    def delete_profile(self):
        name = self.profile_combo.currentText()
        if len(self.context_manager.profiles) <= 1:
            QMessageBox.warning(self, "Error", "Cannot delete the only profile.")
            return
        reply = QMessageBox.question(self, "Delete Profile", f"Delete '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.context_manager.delete_profile(name)
            self.profile_combo.blockSignals(True)
            self.profile_combo.clear()
            self.profile_combo.addItems(list(self.context_manager.profiles.keys()))
            new_name = self.context_manager.active_profile_name
            self.profile_combo.setCurrentText(new_name)
            self.profile_combo.blockSignals(False)
            self.load_profile_fields(new_name)
            self._last_selected_profile = new_name
        
    def upload_pdf_resume(self):
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(self, "Open PDF Resume", "", "PDF Files (*.pdf)")
        if file_path:
            try:
                import fitz
                doc = fitz.open(file_path)
                text = ""
                for page in doc:
                    text += page.get_text() + "\n"
                    
                self._extracted_resume_text = text.strip()
                self.lbl_resume_status.setText(f" ✔ Resume: Loaded ({len(self._extracted_resume_text)} characters) ")
                self.lbl_resume_status.setStyleSheet(
                    "color: #003300; background-color: #00C853; font-weight: bold; "
                    "padding: 3px 10px; border-radius: 8px;"
                )
                QMessageBox.information(self, "Success", "PDF Resume extracted successfully.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not read PDF: {e}")

    def browse_tesseract_path(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Select Tesseract Executable", "", "Executable Files (*.exe);;All Files (*)")
        if path:
            self.tess_path_input.setText(path)

    def setup_other_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        
        inner = QWidget()
        inner.setAutoFillBackground(True)
        inner_layout = QVBoxLayout(inner)
        
        inner_layout.addWidget(_make_section_header("Features", self.theme))
        self.chk_web_search = self._create_toggle_btn(self.config.enable_web_search, "Web Search Enabled", "Web Search Disabled")
        inner_layout.addWidget(self.chk_web_search)
        
        

        
        inner_layout.addSpacing(20)
        inner_layout.addWidget(_make_section_header("Other Shortcuts", self.theme))        
        from PySide6.QtWidgets import QFrame, QFormLayout
        other_hk_frame = QFrame()
        other_hk_frame.setObjectName("OtherHKBox")
        other_hk_frame.setStyleSheet(f"#OtherHKBox {{ border: 1px solid {self.theme.get('border', '#555')}; border-radius: 6px; }}")
        other_hk_layout = QVBoxLayout(other_hk_frame)
        other_hk_layout.setContentsMargins(15, 15, 15, 15)
        
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setVerticalSpacing(15)
        
        self.hint_hotkey_input = self._create_hk_input(getattr(self.config, 'ui_hint_hotkey', 'ctrl+shift+h'))
        form.addRow("Hint Mode Hotkey:", self.hint_hotkey_input)
        
        self.snip_hotkey_input = self._create_hk_input(getattr(self.config, 'ui_snip_hotkey', 'ctrl+shift+p'))
        form.addRow("Snip Mode Hotkey:", self.snip_hotkey_input)
        
        for i in range(1, 4):
            hk = getattr(self.config, f'ui_quick_prompt_{i}_hotkey', f'ctrl+shift+{i}')
            txt = getattr(self.config, f'ui_quick_prompt_{i}_text', '')
            
            hk_input = self._create_hk_input(hk)
            setattr(self, f'qp{i}_hotkey_input', hk_input)
            form.addRow(f"Prompt {i} Hotkey:", hk_input)
            
            txt_input = QLineEdit(txt)
            setattr(self, f'qp{i}_text_input', txt_input)
            form.addRow(f"Prompt {i} Text:", txt_input)
            
        other_hk_layout.addLayout(form)
        inner_layout.addWidget(other_hk_frame)
        
        inner_layout.addSpacing(20)
        inner_layout.addWidget(_make_section_header("Quick Prompts (Silent Triggers)", self.theme))
        inner_layout.addWidget(QLabel("<small><i>These hotkeys instantly send the prompt to Voro, analyzing the current screen.</i></small>"))
        
        from PySide6.QtWidgets import QFormLayout
        for i in range(1, 4):
            hk = getattr(self.config, f'ui_quick_prompt_{i}_hotkey', f'ctrl+shift+{i}')
            txt = getattr(self.config, f'ui_quick_prompt_{i}_text', '')
            
            form = QFormLayout()
            form.setLabelAlignment(Qt.AlignLeft)
            form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
            
            hk_input = self._create_hk_input(hk)
            setattr(self, f'qp{i}_hotkey_input', hk_input)
            form.addRow(f"Prompt {i} Hotkey:", hk_input)
            
            txt_input = QLineEdit(txt)
            setattr(self, f'qp{i}_text_input', txt_input)
            form.addRow(f"Prompt {i} Text:", txt_input)
            
            inner_layout.addLayout(form)
            inner_layout.addSpacing(10)

        inner_layout.addWidget(QLabel("<small><i>Hotkeys take effect instantly upon saving.</i></small>"))

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self.pages.addWidget(page)

    def _sync_active_model_combo(self):
        self.active_model_combo.clear()
        for le in self.model_inputs:
            if le.text().strip():
                self.active_model_combo.addItem(le.text().strip())

    def _sync_active_vision_model_combo(self):
        self.active_vision_model_combo.clear()
        for le in self.vision_model_inputs:
            if le.text().strip():
                self.active_vision_model_combo.addItem(le.text().strip())

    def toggle_key_visibility(self):
        if hasattr(self, 'btn_show_key') and self.btn_show_key.isChecked():
            self.key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_show_key.setText("Hide Key")
        else:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_show_key.setText("Show Key")

    def toggle_premium_key_visibility(self):
        if hasattr(self, 'btn_show_premium_key') and self.btn_show_premium_key.isChecked():
            self.premium_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_show_premium_key.setText("Hide Key")
        else:
            self.premium_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_show_premium_key.setText("Show Key")

    def _validate_premium(self):
        QMessageBox.information(self, "Validation", "Premium API Key validation skipped in offline mode.")



    def save_settings(self):
        self.save_current_profile_fields()
        # Window
        set_key(self.env_path, "UI_OPACITY", str(self.opacity_slider.value()))
        set_key(self.env_path, "UI_THEME_MODE", self.theme_combo.currentText())
        set_key(self.env_path, "UI_FONT_SIZE", str(self.font_slider.value()))
        
        # Audio
        voice_id = self.voice_combo.currentText().split(" ")[0]
        set_key(self.env_path, "UI_VOICE", voice_id)
        
        # Vision
        if hasattr(self, 'chk_vision_enabled'):
            set_key(self.env_path, "UI_VISION_ENABLED", str(self.chk_vision_enabled.isChecked()))
            
        if hasattr(self, 'capture_mode_combo') and hasattr(self, 'capture_target_combo'):
            mode = "monitor" if "Monitor" in self.capture_mode_combo.currentText() else "window"
            target = self.capture_target_combo.currentText()
            if mode == "monitor":
                target = target.replace("Monitor ", "").split(" (")[0]
            set_key(self.env_path, "UI_CAPTURE_MODE", mode)
            set_key(self.env_path, "UI_CAPTURE_TARGET", target)
        
        # Auto Update
        if hasattr(self, 'chk_auto_update'):
            set_key(self.env_path, "UI_AUTO_UPDATE", str(self.chk_auto_update.isChecked()))
        set_key(self.env_path, "CONVERSATION_HISTORY_DEPTH", str(self.hist_slider.value()))
        set_key(self.env_path, "UI_REMEMBER_POSITION", str(self.chk_pos.isChecked()))
        set_key(self.env_path, "MUTE_USER_MIC", str(self.btn_mute_mic.isChecked()))
        set_key(self.env_path, "MUTE_SYSTEM_AUDIO", str(self.btn_mute_sys.isChecked()))
        if hasattr(self, 'you_heading_color'):
            set_key(self.env_path, "UI_YOU_HEADING_COLOR", self.you_heading_color)
        if hasattr(self, 'interviewer_heading_color'):
            set_key(self.env_path, "UI_INTERVIEWER_HEADING_COLOR", self.interviewer_heading_color)
        if hasattr(self, 'voro_heading_color'):
            set_key(self.env_path, "UI_VORO_HEADING_COLOR", self.voro_heading_color)

        # Shortcuts
        if hasattr(self, 'hotkey_input'): set_key(self.env_path, "UI_GLOBAL_HOTKEY", self.hotkey_input.text().strip())
        if hasattr(self, 'stop_hotkey_input'): set_key(self.env_path, "UI_STOP_HOTKEY", self.stop_hotkey_input.text().strip())
        if hasattr(self, 'qp1_hotkey_input'):
            for i in range(1, 4):
                set_key(self.env_path, f"UI_QUICK_PROMPT_{i}_HOTKEY", getattr(self, f'qp{i}_hotkey_input').text().strip())
                set_key(self.env_path, f"UI_QUICK_PROMPT_{i}_TEXT", getattr(self, f'qp{i}_text_input').text().strip())

        if hasattr(self, 'hint_hotkey_input'): set_key(self.env_path, "UI_HINT_HOTKEY", self.hint_hotkey_input.text().strip())
        if hasattr(self, 'snip_hotkey_input'): set_key(self.env_path, "UI_SNIP_HOTKEY", self.snip_hotkey_input.text().strip())
        if hasattr(self, 'maximize_hotkey_input'): set_key(self.env_path, "UI_MAXIMIZE_HOTKEY", self.maximize_hotkey_input.text().strip())
        if hasattr(self, 'clear_session_hotkey_input'): set_key(self.env_path, "UI_CLEAR_SESSION_HOTKEY", self.clear_session_hotkey_input.text().strip())
        if hasattr(self, 'toggle_tray_hotkey_input'): set_key(self.env_path, "UI_TOGGLE_TRAY_HOTKEY", self.toggle_tray_hotkey_input.text().strip())
        if hasattr(self, 'stealth_hotkey_input'): set_key(self.env_path, "UI_STEALTH_HOTKEY", self.stealth_hotkey_input.text().strip())
        if hasattr(self, 'stealth_toggle_btn'): set_key(self.env_path, "UI_STEALTH_MODE", str(self.stealth_toggle_btn.isChecked() if hasattr(self.stealth_toggle_btn, 'isChecked') else self.stealth_toggle_btn.property("active") or False))
        if hasattr(self, 'tts_mute_hotkey_input'): set_key(self.env_path, "UI_TTS_MUTE_HOTKEY", self.tts_mute_hotkey_input.text().strip())
        if hasattr(self, 'taskbar_hotkey_input'): set_key(self.env_path, "UI_TASKBAR_TOGGLE_HOTKEY", self.taskbar_hotkey_input.text().strip())
        if hasattr(self, 'quit_hotkey_input'): set_key(self.env_path, "UI_QUIT_HOTKEY", self.quit_hotkey_input.text().strip())
        if hasattr(self, 'mute_mic_hotkey_input'): set_key(self.env_path, "UI_MUTE_MIC_HOTKEY", self.mute_mic_hotkey_input.text().strip())
        if hasattr(self, 'mute_sys_hotkey_input'): set_key(self.env_path, "UI_MUTE_SYS_HOTKEY", self.mute_sys_hotkey_input.text().strip())
        if hasattr(self, 'cycle_mode_hotkey_input'): set_key(self.env_path, "UI_CYCLE_MODE_HOTKEY", self.cycle_mode_hotkey_input.text().strip())

        # Audio page additions
        if hasattr(self, 'user_device_combo'):
            set_key(self.env_path, "USER_AUDIO_DEVICE", self.user_device_combo.currentText().strip())
        if hasattr(self, 'sys_device_combo'):
            set_key(self.env_path, "SYSTEM_AUDIO_DEVICE", self.sys_device_combo.currentText().strip())
        if hasattr(self, 'tts_vol_slider'):
            set_key(self.env_path, "UI_TTS_VOLUME", str(self.tts_vol_slider.value()))
        if hasattr(self, 'tts_speed_combo'):
            set_key(self.env_path, "UI_TTS_RATE", self.tts_speed_combo.currentText().strip())
        if hasattr(self, 'tts_output_device_combo'):
            set_key(self.env_path, "UI_TTS_OUTPUT_DEVICE", self.tts_output_device_combo.currentText().strip())

        # Other
        if hasattr(self, 'chk_web_search'):
            set_key(self.env_path, "ENABLE_WEB_SEARCH", str(self.chk_web_search.isChecked()))
        if hasattr(self, 'chk_auto_monitor'):
            set_key(self.env_path, "ENABLE_AUTO_MONITOR", str(self.chk_auto_monitor.isChecked()))
        if hasattr(self, 'ocr_device_combo'):
            set_key(self.env_path, "OCR_COMPUTE_DEVICE", self.ocr_device_combo.currentText().strip())
        if hasattr(self, 'tess_path_input'):
            set_key(self.env_path, "TESSERACT_CMD_PATH", self.tess_path_input.text().strip())
        if hasattr(self, 'ai_tone_combo'):
            set_key(self.env_path, "AI_TONE", self.ai_tone_combo.currentText().strip())
        if hasattr(self, 'stt_device_combo'):
            set_key(self.env_path, "STT_DEVICE", self.stt_device_combo.currentText().strip())
        if hasattr(self, 'stt_model_combo'):
            set_key(self.env_path, "STT_MODEL_SIZE", self.stt_model_combo.currentText().strip())
        if hasattr(self, 'stt_dir_input'):
            val = self.stt_dir_input.text().strip() or self.dl_dir_input.text().strip()
            set_key(self.env_path, "STT_MODEL_DIR", val)
        if hasattr(self, 'stt_context_input'):
            set_key(self.env_path, "STT_CONTEXT_PROMPT", self.stt_context_input.toPlainText().strip())
        if hasattr(self, 'groq_api_input'):
            set_key(self.env_path, "GROQ_API_KEY", self.groq_api_input.text().strip())

        if hasattr(self, 'chk_tts_muted'):
            set_key(self.env_path, "UI_TTS_MUTED", str(self.btn_tts_muted.isChecked()))

        import subprocess
        import sys
        from PySide6.QtWidgets import QApplication
        
        self.accept()
        subprocess.Popen([sys.executable] + sys.argv)
        QApplication.quit()

    def _heading_btn_style(self, hex_color: str) -> str:
        """Returns QSS for a heading preview button: coloured text on a subtle bg."""
        from PySide6.QtGui import QColor
        c = QColor(hex_color)
        # semi-transparent version of the colour as background
        bg = f"rgba({c.red()},{c.green()},{c.blue()},0.15)"
        return (
            f"color: {hex_color}; background-color: {bg}; "
            f"border: 1px solid {hex_color}; border-radius: 8px; "
            f"font-size: 15px; font-weight: 700; letter-spacing: 1px; padding: 4px 12px;"
        )

    def pick_you_color(self):
        color = QColorDialog.getColor(QColor(self.you_heading_color), self, "Select YOU Heading Color")
        if color.isValid():
            self.you_heading_color = color.name()
            self.btn_you_color.setStyleSheet(self._heading_btn_style(self.you_heading_color))

    def pick_interviewer_color(self):
        color = QColorDialog.getColor(QColor(self.interviewer_heading_color), self, "Select INTERVIEWER Heading Color")
        if color.isValid():
            self.interviewer_heading_color = color.name()
            self.btn_interviewer_color.setStyleSheet(self._heading_btn_style(self.interviewer_heading_color))

    def pick_voro_color(self):
        color = QColorDialog.getColor(QColor(self.voro_heading_color), self, "Select VORO Heading Color")
        if color.isValid():
            self.voro_heading_color = color.name()
            self.btn_voro_color.setStyleSheet(self._heading_btn_style(self.voro_heading_color))

    @Slot(bool)
    def _on_vision_toggled(self, checked):
        if hasattr(self, 'capture_mode_combo'):
            self.capture_mode_combo.setEnabled(checked)
        if hasattr(self, 'capture_target_combo'):
            self.capture_target_combo.setEnabled(checked)
        if hasattr(self, 'preview_label'):
            if checked:
                self._update_preview()
            else:
                self.preview_label.setText("Vision Disabled")
                from PySide6.QtGui import QPixmap
                self.preview_label.setPixmap(QPixmap())

    @Slot()
    def _apply_fetched_windows(self):
        if hasattr(self, '_temp_window_titles'):
            self.capture_target_combo.clear()
            self.capture_target_combo.addItems(self._temp_window_titles)
            self.capture_target_combo.setEnabled(True)

    def _update_preview(self):
        text = self.capture_target_combo.currentText()
        if not text or text == "Fetching windows...":
            self.preview_label.setText("No Preview")
            return
            
        mode = "monitor" if "Monitor" in self.capture_mode_combo.currentText() else "window"
        target = text
        if mode == "monitor":
            target = target.replace("Monitor ", "").split(" (")[0]
            
        import mss, ctypes
        from ctypes import wintypes
        from PySide6.QtGui import QImage, QPixmap
        
        try:
            with mss.mss() as sct:
                if mode == "window":
                    hwnd = ctypes.windll.user32.FindWindowW(None, target)
                    if hwnd:
                        rect = wintypes.RECT()
                        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        bbox = {"left": rect.left, "top": rect.top, "width": max(1, rect.right - rect.left), "height": max(1, rect.bottom - rect.top)}
                        sct_img = sct.grab(bbox)
                    else:
                        self.preview_label.setText("Window not found")
                        return
                else:
                    idx = int(target)
                    monitors = sct.monitors
                    if idx >= len(monitors): idx = 1
                    sct_img = sct.grab(monitors[idx])
                    
                img = QImage(sct_img.bgra, sct_img.width, sct_img.height, QImage.Format_RGB32)
                pixmap = QPixmap.fromImage(img)
                pixmap = pixmap.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview_label.setPixmap(pixmap)
        except Exception as e:
            self.preview_label.setText("Preview Error")

    def _update_capture_targets(self, text):
        self.capture_target_combo.clear()
        if text == "Monitor":
            self.capture_target_combo.setEnabled(True)
            import mss
            names_by_pos = {}
            try:
                from PySide6.QtGui import QGuiApplication
                if QGuiApplication.instance():
                    screens = QGuiApplication.instance().screens()
                    names_by_pos = {(s.geometry().x(), s.geometry().y()): s.name() for s in screens}
            except Exception:
                pass

            with mss.mss() as sct:
                for i in range(1, len(sct.monitors)):
                    m = sct.monitors[i]
                    name = names_by_pos.get((m['left'], m['top']), "")
                    name_suffix = f" ({name})" if name else ""
                    self.capture_target_combo.addItem(f"Monitor {i}{name_suffix}")
        else:
            self.capture_target_combo.addItem("Fetching windows...")
            self.capture_target_combo.setEnabled(False)
            import threading
            def fetch():
                import ctypes
                titles = []
                EnumWindows = ctypes.windll.user32.EnumWindows
                EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
                GetWindowText = ctypes.windll.user32.GetWindowTextW
                GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
                IsWindowVisible = ctypes.windll.user32.IsWindowVisible
                def foreach_window(hwnd, lParam):
                    if IsWindowVisible(hwnd):
                        length = GetWindowTextLength(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            GetWindowText(hwnd, buff, length + 1)
                            titles.append(buff.value)
                    return True
                EnumWindows(EnumWindowsProc(foreach_window), 0)
                self._temp_window_titles = sorted(list(set(titles)))
                from PySide6.QtCore import QMetaObject, Qt
                QMetaObject.invokeMethod(self, "_apply_fetched_windows", Qt.QueuedConnection)
            threading.Thread(target=fetch, daemon=True).start()

    def setup_updates_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        from app.core.version import APP_VERSION
        layout.addWidget(QLabel(f"<h2>Current Version: {APP_VERSION}</h2>"))
        
        self.btn_check_update = QPushButton("Check for Updates")
        self.btn_check_update.setCursor(Qt.PointingHandCursor)
        self.btn_check_update.clicked.connect(self._check_for_updates)
        layout.addWidget(self.btn_check_update)
        layout.addStretch()
        
        self.pages.addWidget(page)

    def setup_help_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)
        
        content_layout.addWidget(QLabel("<h2>Help Center</h2>"))
        
        # --- Dropdown 1: Setup ---
        box_setup = CollapsibleBox("🚀 How to Use the App (Setup Guide)")
        lbl_setup = QLabel(
            "<b>Step 1 — Lightning-Fast Voice (Groq API)</b><br>"
            "To get the fastest possible voice response times (under 200ms), we recommend setting up Groq. Go to <b>console.groq.com</b>, create a free API key, and paste it into the <b>Groq API Key</b> field in the <b>Audio</b> settings tab.<br><br>"
            "<b>Step 2 — Offline Voice Fallback (STT)</b><br>"
            "If your internet drops or Groq is unavailable, Voro will instantly fall back to a local offline voice model. To set this up, go to the <b>Audio</b> tab, click 'Browse' to set an STT Models Directory (e.g., inside your Voro folder), and then click 'Save & Restart'. It will download the fallback model automatically.<br><br>"
            "<i>Note: Voro's Brain and Screen Vision systems are entirely fully-managed. You don't need to configure anything else to get started!</i>"
        )
        lbl_setup.setWordWrap(True)
        lbl_setup.setStyleSheet(f"color: {self.theme.get('base_text', '#E8E8E8')}; line-height: 1.4;")
        box_setup.addWidget(lbl_setup)
        content_layout.addWidget(box_setup)
        
        # --- Dropdown 2: Help ---
        box_help = CollapsibleBox("📖 Voro Controls & Features")
        lbl_help = QLabel(
            "<b>Hotkeys:</b><br>"
            "<i>(You can change all these hotkeys to whatever you like in the 'Interface' settings tab)</i><br><br>"
            f"• <code>{self.config.ui_global_hotkey}</code> : Wake Voro up and start talking.<br>"
            f"• <code>{self.config.ui_hint_hotkey}</code> : Toggle Hint Mode (Answers appear subtly in the text box instead of being spoken).<br>"
            f"• <code>{self.config.ui_snip_hotkey}</code> : Toggle Snip Mode (Select exactly what part of the screen Voro sees).<br>"
            f"• <code>{self.config.ui_stealth_hotkey}</code> : Toggle Stealth Mode (Completely hides Voro from Zoom/Teams screenshares and screenshots).<br>"
            f"• <code>{self.config.ui_stop_hotkey}</code> : Stop Voro's current action or speech.<br>"
            f"• <code>{self.config.ui_clear_session_hotkey}</code> : Clear Session (Make Voro forget the conversation).<br>"
            f"• <code>{self.config.ui_mute_mic_hotkey}</code> : Mute User Mic.<br>"
            f"• <code>{self.config.ui_mute_sys_hotkey}</code> : Mute System Audio capture.<br>"
            f"• <code>{self.config.ui_tts_mute_hotkey}</code> : Mute Voro's Voice.<br>"
            f"• <code>{self.config.ui_taskbar_hotkey}</code> : Toggle Taskbar visibility.<br>"
            f"• <code>{self.config.ui_toggle_tray_hotkey}</code> : Toggle System Tray icon.<br>"
            f"• <code>{self.config.ui_cycle_mode_hotkey}</code> : Cycle Voro Interface Mode.<br>"
            f"• <code>{self.config.ui_quick_prompt_1_hotkey}</code> / <code>2</code> / <code>3</code> : Trigger Quick Prompts.<br><br>"
            "<b>Tips:</b><br>"
            "Use the <b>Occupancy</b> slider on Voro's main bar to adjust transparency. You can pull it down to make Voro nearly invisible during an interview!"
        )
        lbl_help.setWordWrap(True)
        lbl_help.setStyleSheet(f"color: {self.theme.get('base_text', '#E8E8E8')}; line-height: 1.4;")
        box_help.addWidget(lbl_help)
        content_layout.addWidget(box_help)
        
        # --- Dropdown 3: Support ---
        box_support = CollapsibleBox("🛠️ Support & Logs")
        
        support_lbl = QLabel(
            "If you encounter issues or crashes with Voro, you can check your system logs or copy them to report a bug to our engineering team.<br><br>"
            "<b>Contact Norvi Agency Support:</b><br>"
            "Website: <a href='https://nor-vi.in/contact/' style='color:#0055A4; text-decoration:none;'>https://nor-vi.in/contact/</a><br>"
        )
        support_lbl.setWordWrap(True)
        support_lbl.setOpenExternalLinks(True)
        support_lbl.setStyleSheet(f"color: {self.theme.get('base_text', '#E8E8E8')}; line-height: 1.4;")
        box_support.addWidget(support_lbl)
        
        btn_layout = QHBoxLayout()
        self.btn_open_logs = QPushButton("Open Log Folder")
        self.btn_open_logs.setCursor(Qt.PointingHandCursor)
        self.btn_open_logs.clicked.connect(self._open_log_folder)
        btn_layout.addWidget(self.btn_open_logs)
        
        self.btn_copy_logs = QPushButton("Copy Logs to Clipboard")
        self.btn_copy_logs.setCursor(Qt.PointingHandCursor)
        self.btn_copy_logs.clicked.connect(self._copy_logs)
        btn_layout.addWidget(self.btn_copy_logs)
        btn_layout.addStretch()
        
        box_support.addLayout(btn_layout)
        content_layout.addWidget(box_support)
        
        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        self.pages.addWidget(page)
        
    def _open_log_folder(self):
        import os, subprocess
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        os.startfile(log_dir)
        
    def _check_for_updates(self):
        self.btn_check_update.setText("Checking...")
        self.btn_check_update.setEnabled(False)
        from app.core.updater import Updater
        self._temp_updater = Updater()
        self._temp_updater.update_available.connect(self._on_update_found)
        self._temp_updater.no_update.connect(self._on_no_update)
        self._temp_updater.check_error.connect(self._on_update_error)
        self._temp_updater.check_for_updates()
        
    def _on_update_found(self, version, notes, url):
        self.btn_check_update.setText("Check for Updates")
        self.btn_check_update.setEnabled(True)
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "Update Voro", f"Version {version} is available!\n\nRelease Notes:\n{notes}\n\nDo you want to download and install it now?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.btn_check_update.setText("Downloading...")
            self.btn_check_update.setEnabled(False)
            self._temp_updater.download_progress.connect(lambda p: self.btn_check_update.setText(f"D/L: {p}%"))
            self._temp_updater.download_error.connect(lambda e: self.btn_check_update.setText("Failed"))
            self._temp_updater.download_and_install(url)

    def _on_no_update(self):
        self.btn_check_update.setText("Check for Updates")
        self.btn_check_update.setEnabled(True)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Up to date", "You are running the latest version of Voro.")
        
    def _on_update_error(self, err):
        self.btn_check_update.setText("Check for Updates")
        self.btn_check_update.setEnabled(True)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Update Failed", f"Could not check for updates: {err}")


    
    def _browse_stt_dir(self):
        from PySide6.QtWidgets import QFileDialog
        dir_path = QFileDialog.getExistingDirectory(self, "Select STT Models Directory")
        if dir_path:
            self.stt_dir_input.setText(dir_path)
            self.dl_dir_input.setText(dir_path) # Sync with download dir
    def _browse_dl_dir(self):
        from PySide6.QtWidgets import QFileDialog
        dir_path = QFileDialog.getExistingDirectory(self, "Select Model Save Directory")
        if dir_path:
            self.dl_dir_input.setText(dir_path)

    def _start_model_dl(self):
        model = self.dl_model_combo.currentText()
        dl_dir = self.dl_dir_input.text()
        
        self.btn_dl_start.setEnabled(False)
        self.btn_dl_pause.setEnabled(True)
        self.btn_dl_pause.setText("Pause")
        self.btn_dl_cancel.setEnabled(True)
        self.dl_status_lbl.setText(f"Connecting to Hugging Face...")
        
        
        self.dl_thread = ModelDownloadThread(model, dl_dir)
        self.dl_thread.progress.connect(self._update_dl_progress)
        self.dl_thread.finished.connect(self._dl_finished)
        self.dl_thread.start()

    def _update_dl_progress(self, downloaded, total, msg):
        
        
        self.dl_status_lbl.setText(msg)

    def _dl_finished(self, success, msg):
        self.btn_dl_start.setEnabled(True)
        self.btn_dl_pause.setEnabled(False)
        self.btn_dl_cancel.setEnabled(False)
        
        self.dl_status_lbl.setText(msg)

    def _pause_model_dl(self):
        if hasattr(self, 'dl_thread') and self.dl_thread.isRunning():
            if self.btn_dl_pause.text() == "Pause":
                self.dl_thread.is_paused = True
                self.btn_dl_pause.setText("Resume")
                self.dl_status_lbl.setText("Paused")
            else:
                self.dl_thread.is_paused = False
                self.btn_dl_pause.setText("Pause")
                self.dl_status_lbl.setText("Resuming...")

    def _cancel_model_dl(self):
        if hasattr(self, 'dl_thread') and self.dl_thread.isRunning():
            self.dl_thread.is_cancelled = True
        
        self.btn_dl_start.setEnabled(True)
        self.btn_dl_pause.setEnabled(False)
        self.btn_dl_pause.setText("Pause")
        self.btn_dl_cancel.setEnabled(False)
        
        self.dl_status_lbl.setText("Cancelling...")

    def _copy_logs(self):
        import os
        from PySide6.QtWidgets import QApplication
        log_file = os.path.join(os.getcwd(), "logs", "voro.log")
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                logs = f.read()
            # Grab last 20000 chars to avoid clipboard bloat
            logs = logs[-20000:]
            QApplication.clipboard().setText(logs)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Copied", "Recent logs copied to clipboard.")
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Logs", "No log file found yet.")

    def setup_norvi_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        
        inner_layout.addWidget(QLabel("<h2>Norvi Agent Credentials</h2>"))
        
        import json, os, base64, time as _time
        lease_file = os.path.join(os.path.expanduser("~"), ".norvi_voro_lease")
        
        license_id = ""
        device_id = ""
        product = ""
        expires_str = ""
        status = "Not Activated"
        
        if os.path.exists(lease_file):
            try:
                with open(lease_file, "r") as f:
                    data = json.load(f)
                token = data.get("token", "")
                expires_at = data.get("expires_at", 0)
                if token:
                    parts = token.split(".")
                    if len(parts) >= 2:
                        payload_b64 = parts[1]
                        payload_b64 += "=" * (-len(payload_b64) % 4)
                        decoded = json.loads(base64.b64decode(payload_b64).decode())
                        license_id = decoded.get("license_id", "")
                        device_id = decoded.get("device_id", "")
                        product = decoded.get("product", "voro").capitalize()
                if expires_at:
                    import datetime
                    exp_dt = datetime.datetime.fromtimestamp(expires_at)
                    expires_str = exp_dt.strftime("%d %b %Y, %I:%M %p")
                    status = "Active" if _time.time() < expires_at else "Expired"
            except Exception as e:
                status = f"Error: {e}"
        
        from PySide6.QtWidgets import QFormLayout
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setVerticalSpacing(12)
        
        def _ro_field(val):
            f = QLineEdit()
            f.setText(val)
            f.setReadOnly(True)
            f.setStyleSheet("background: #1a1a1a; color: #aaaaaa;")
            return f
        
        form.addRow("Status:", _ro_field(status))
        form.addRow("Product:", _ro_field(product or "Voro"))
        form.addRow("License ID:", _ro_field(license_id or "Not found"))
        form.addRow("Device ID:", _ro_field(device_id or "Not found"))
        form.addRow("Expires:", _ro_field(expires_str or "Unknown"))
        
        inner_layout.addLayout(form)
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self.pages.addWidget(page)
