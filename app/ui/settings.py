from PySide6.QtCore import Slot
import os
import sys
from dotenv import set_key
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QMessageBox, QSlider, QColorDialog,
                               QListWidget, QStackedWidget, QWidget, QCheckBox, QComboBox, QTextEdit, QScrollArea,
                               QRadioButton, QGroupBox, QButtonGroup, QFrame)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from app.utils.logging import logger
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
            import huggingface_hub.utils as hf_utils
            import huggingface_hub.file_download as hf_dl
            
            # Store original references to restore later
            orig_utils_tqdm = getattr(hf_utils, 'tqdm', None)
            orig_dl_tqdm = getattr(hf_dl, 'tqdm', None)
            
            # Patch everywhere
            hf_utils.tqdm = CustomTqdm
            hf_dl.tqdm = CustomTqdm
            
            try:
                import importlib
                hf_prog = importlib.import_module("huggingface_hub.utils._progress")
                orig_prog_tqdm = getattr(hf_prog, 'tqdm', None)
                hf_prog.tqdm = CustomTqdm
            except Exception:
                orig_prog_tqdm = None
            
            import os
            if self.download_dir.strip():
                base_dir = self.download_dir
            else:
                appdata = os.environ.get('APPDATA', os.path.expanduser("~"))
                base_dir = os.path.join(appdata, "Norvi", "Voro", "STT_Models")
            target_dir = os.path.join(base_dir, f"faster-whisper-{self.model_size}")
            os.makedirs(target_dir, exist_ok=True)
            
            snapshot_download(repo_id=repo_id, local_dir=target_dir, local_dir_use_symlinks=False)
            
            self.finished.emit(True, f"Saved to {target_dir}")
        except InterruptedError as e:
            self.finished.emit(False, str(e))
        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            hf_utils.tqdm = orig_utils_tqdm
            hf_dl.tqdm = orig_dl_tqdm
            if orig_prog_tqdm is not None:
                try:
                    import importlib
                    hf_prog = importlib.import_module("huggingface_hub.utils._progress")
                    hf_prog.tqdm = orig_prog_tqdm
                except Exception:
                    pass

class CollapsibleBox(QWidget):
    def __init__(self, title="", parent=None, is_dark=None):
        super().__init__(parent)
        if is_dark is None:
            if hasattr(parent, 'theme'):
                is_dark = parent.theme.get('bg', '#1E1E1E') == '#1E1E1E'
            else:
                try:
                    from app.ui.theme import is_windows_dark_mode
                    is_dark = is_windows_dark_mode()
                except Exception:
                    is_dark = True

        btn_bg = "#2D333B" if is_dark else "#F6F8FA"
        btn_fg = "#FFFFFF" if is_dark else "#1F2328"
        btn_border = "#444C56" if is_dark else "#D0D7DE"
        btn_hover = "#373E47" if is_dark else "#ECEFF2"
        btn_checked = "#1E2329" if is_dark else "#EAEFF5"

        self.toggle_button = QPushButton(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: 12px 15px;
                background-color: {btn_bg};
                color: {btn_fg};
                border: 1px solid {btn_border};
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
            }}
            QPushButton:checked {{
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                border-bottom: none;
                background-color: {btn_checked};
            }}
        """)
        
        self.content_area = QWidget()
        self.content_area.setStyleSheet(f"""
            QWidget#content_area {{
                background-color: transparent;
                border: 1px solid {btn_border};
                border-top: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }}
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

    def expand(self):
        self.toggle_button.setChecked(True)

    def collapse(self):
        self.toggle_button.setChecked(False)

class SettingsDialog(QDialog):
    def __init__(self, context_manager: ContextManager, parent=None):
        super().__init__(parent)
        is_stealth = bool(parent and getattr(parent, '_stealth_active', False))
        if is_stealth:
            self.setWindowTitle("")
            self.setWindowFlags(self.windowFlags() | Qt.Tool)
        else:
            self.setWindowTitle("Voro Settings")
        
        self.config = load_config()
        
        from PySide6.QtCore import QSettings
        self._qsettings = QSettings("Norvi", "Voro")
        geom = self._qsettings.value("settings_geometry")
        if geom:
            self.restoreGeometry(geom)
        else:
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
        from app.core.config import get_env_path
        self.env_path = get_env_path()
        
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
        QMessageBox {{
            background-color: {bg_main};
            color: {text_col};
        }}
        QMessageBox QLabel {{
            color: {text_col};
            font-size: 13px;
            background-color: transparent;
        }}
        QMessageBox QPushButton {{
            background-color: {accent};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 6px 20px;
            font-weight: bold;
            font-size: 13px;
            min-width: 70px;
        }}
        QMessageBox QPushButton:hover {{
            background-color: #004080;
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
        sig_link_col = "#38BDF8" if is_dark else "#0055A4"
        self.sig_label = QLabel(f"Designed and Developed by <a href='https://nor-vi.in/' style='color:{sig_link_col}; text-decoration:none;'>Norvi Agency</a>")
        self.sig_label.setOpenExternalLinks(True)
        self.sig_label.setAlignment(Qt.AlignRight)
        self.sig_label.setStyleSheet(f"font-size: 11px; color: {self.theme.get('base_text', '#888')}; margin-bottom: 10px;")
        right_layout.addWidget(self.sig_label)
        
        # Action Buttons (Bottom)
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save && Restart")
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
        is_dark = self.theme.get('bg', '#1E1E1E') == '#1E1E1E'
        disabled_bg = "#444444" if is_dark else "#E5E5E5"
        disabled_fg = "#AAAAAA" if is_dark else "#555555"
        disabled_border = "#555555" if is_dark else "#CCCCCC"

        def _update(checked):
            is_active = not checked if inverted else checked
            if is_active:
                btn.setText(text_enabled)
                btn.setStyleSheet("QPushButton { background-color: #0078D7; color: white; border: none; padding: 6px; border-radius: 4px; font-weight: bold; }")
            else:
                btn.setText(text_disabled)
                btn.setStyleSheet(f"QPushButton {{ background-color: {disabled_bg}; color: {disabled_fg}; border: 1px solid {disabled_border}; padding: 6px; border-radius: 4px; font-weight: bold; }}")
        btn.toggled.connect(_update)
        _update(default_checked)
        return btn

    def showEvent(self, event):
        super().showEvent(event)
        # Apply stealth mode to this dialog if the parent window has it enabled
        if self.parent() and getattr(self.parent(), '_stealth_active', False):
            self.setWindowTitle("")
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
        
        self.chk_auto_answer = self._create_toggle_btn(getattr(self.config, 'ui_auto_answer', True), "Auto-Answer Questions: ENABLED", "Auto-Answer Questions: DISABLED (Manual Mode)")
        layout.addWidget(self.chk_auto_answer)
        
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
        self.stt_dir_input.setPlaceholderText("Default (Matches Model Save Directory)")
        
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
        self.dl_dir_input.setPlaceholderText("Default (%APPDATA%\\Norvi\\Voro\\STT_Models)")
        
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
        
        self.auto_answer_hotkey_input = self._create_hk_input(getattr(self.config, 'ui_auto_answer_hotkey', 'ctrl+shift+u'))
        form.addRow("Toggle Auto-Answer Hotkey:", self.auto_answer_hotkey_input)
        
        self.manual_answer_hotkey_input = self._create_hk_input(getattr(self.config, 'ui_manual_answer_hotkey', 'ctrl+enter'))
        form.addRow("Trigger Manual Answer Hotkey:", self.manual_answer_hotkey_input)
        
        hk_layout.addLayout(form)
        layout.addWidget(hk_frame)
        
        # --- Stealth Mode Toggle ---
        from app.utils.logging import logger as _logger
        stealth_header = _make_section_header("Stealth Mode", self.theme)
        layout.addWidget(stealth_header)
        
        stealth_hint = QLabel("When Stealth Mode is ON, Voro is completely invisible to screen recording,\nscreenshots, and screenshares. Toggle with the hotkey above or the button below.")
        stealth_hint.setWordWrap(True)
        is_dark = self.theme.get('bg', '#1E1E1E') == '#1E1E1E'
        hint_col = "#aaaaaa" if is_dark else "#555555"
        stealth_hint.setStyleSheet(f"color: {hint_col}; font-size: 12px;")
        layout.addWidget(stealth_hint)
        
        stealth_val = getattr(self.config, 'ui_stealth_mode', False)
        self.stealth_toggle_btn = self._create_toggle_btn(stealth_val, "Stealth Mode: ON", "Stealth Mode: OFF")
        layout.addWidget(self.stealth_toggle_btn)


        layout.addStretch()
        scroll.setWidget(inner)
        main_layout.addWidget(scroll)
        self.pages.addWidget(page)
        
    def _open_setup_browser(self):
        import webbrowser
        webbrowser.open("https://ollama.com/download/OllamaSetup.exe")

    def _navigate_to_setup(self):
        self.sidebar.setCurrentRow(8)
        if hasattr(self, 'box_setup'):
            self.box_setup.expand()
        
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
        
        is_dark = self.theme.get('bg', '#1E1E1E') == '#1E1E1E'
        disabled_bg = "#444444" if is_dark else "#E5E5E5"
        disabled_fg = "#AAAAAA" if is_dark else "#555555"
        disabled_border = "#555555" if is_dark else "#CCCCCC"

        def _toggle_mic(checked):
            self.user_device_combo.setEnabled(not checked)
            if checked:
                self.btn_mute_mic.setText("User Mic Disabled")
                self.btn_mute_mic.setStyleSheet(f"QPushButton {{ background-color: {disabled_bg}; color: {disabled_fg}; border: 1px solid {disabled_border}; padding: 6px; border-radius: 4px; font-weight: bold; }}")
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
                self.btn_mute_sys.setStyleSheet(f"QPushButton {{ background-color: {disabled_bg}; color: {disabled_fg}; border: 1px solid {disabled_border}; padding: 6px; border-radius: 4px; font-weight: bold; }}")
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
        
        # Development Warning Banner
        warn_box = QFrame()
        warn_bg = "#2D2206" if is_dark else "#FFF8E1"
        warn_border = "#B27B00" if is_dark else "#FFE082"
        warn_text = "#FFE082" if is_dark else "#8C5400"
        warn_box.setStyleSheet(f"QFrame {{ background-color: {warn_bg}; border: 1px solid {warn_border}; border-radius: 6px; }}")
        warn_box_layout = QVBoxLayout(warn_box)
        warn_box_layout.setContentsMargins(10, 8, 10, 8)
        
        warn_title = QLabel("⚠️ Development Notice:")
        warn_title.setStyleSheet(f"font-weight: bold; color: {warn_text}; font-size: 11px; border: none; background: transparent;")
        warn_box_layout.addWidget(warn_title)
        
        warn_msg = QLabel("Voro Voice is an experimental feature currently under active development. It is not supported or isolated on all devices. Do not use for interviews without checking and testing first.")
        warn_msg.setWordWrap(True)
        warn_msg.setStyleSheet(f"color: {warn_text}; font-size: 11px; border: none; background: transparent;")
        warn_box_layout.addWidget(warn_msg)
        
        tts_layout.addWidget(warn_box)
        
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
                self.btn_tts_muted.setStyleSheet(f"QPushButton {{ background-color: {disabled_bg}; color: {disabled_fg}; border: 1px solid {disabled_border}; padding: 6px; border-radius: 4px; font-weight: bold; }}")
            else:
                self.btn_tts_muted.setText("Voro Voice (TTS) Enabled")
                self.btn_tts_muted.setStyleSheet("QPushButton { background-color: #0078D7; color: white; border: none; padding: 6px; border-radius: 4px; font-weight: bold; }")
            
        self.btn_tts_muted.toggled.connect(_toggle_tts)
        _toggle_tts(self.btn_tts_muted.isChecked())

        def _on_tts_clicked():
            if not self.btn_tts_muted.isChecked():
                from PySide6.QtWidgets import QMessageBox
                from app.ui.theme import style_message_box
                box = QMessageBox(self)
                theme_mode = getattr(self.config, 'ui_theme_mode', 'system')
                style_message_box(box, theme_mode=theme_mode, parent=self)
                box.setIcon(QMessageBox.Icon.Warning)
                box.setWindowTitle("Experimental Feature Notice")
                box.setText(
                    "<b>Voro Voice is currently in development.</b><br><br>"
                    "This feature is not supported or isolated on all devices.<br><br>"
                    "<b>Do not use this for interviews without testing your device setup first.</b>"
                )
                box.setStandardButtons(QMessageBox.StandardButton.Ok)
                if not os.environ.get("PYTEST_CURRENT_TEST"):
                    box.exec()
        self.btn_tts_muted.clicked.connect(_on_tts_clicked)
        
        inner_layout.addWidget(tts_frame)
        
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self.pages.addWidget(page)

    def _reset_test_voice_btn(self):
        """Resets the Test Voice button state."""
        if hasattr(self, 'btn_test_voice') and self.btn_test_voice:
            self.btn_test_voice.setText("Test Voice")
            if hasattr(self, 'btn_tts_muted') and self.btn_tts_muted:
                self.btn_test_voice.setEnabled(not self.btn_tts_muted.isChecked())
            else:
                self.btn_test_voice.setEnabled(True)

    def _test_voice(self):
        if hasattr(self, '_test_player') and self._test_player:
            try:
                self._test_player.stop()
            except Exception:
                pass

        voice_id = self.voice_combo.currentText().split(" ")[0].strip()
        speed_rate = self.tts_speed_combo.currentText().strip() if hasattr(self, 'tts_speed_combo') else '+0%'
        
        self.btn_test_voice.setText("Playing...")
        self.btn_test_voice.setEnabled(False)

        # Safety watchdog timer: resets button in 8 seconds regardless of network or media stalls
        from PySide6.QtCore import QTimer
        if hasattr(self, '_test_watchdog') and self._test_watchdog:
            self._test_watchdog.stop()
        self._test_watchdog = QTimer(self)
        self._test_watchdog.setSingleShot(True)
        self._test_watchdog.timeout.connect(self._reset_test_voice_btn)
        self._test_watchdog.start(8000)

        import threading
        def fetch_audio():
            import tempfile, time, os
            tmp_dir = os.path.join(tempfile.gettempdir(), "Voro_TTS_Test")
            os.makedirs(tmp_dir, exist_ok=True)
            mp3_path = os.path.join(tmp_dir, f"test_voice_{int(time.time()*1000)}.mp3")
            
            # 1. Attempt Edge TTS
            try:
                import edge_tts, asyncio
                async def run_edge():
                    comm = edge_tts.Communicate("Hello, I am Voro. This is how I sound.", voice_id, rate=speed_rate)
                    await comm.save(mp3_path)
                asyncio.run(asyncio.wait_for(run_edge(), timeout=4.5))
                if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
                    return mp3_path
            except Exception as e:
                logger.warning(f"[settings] Test voice Edge TTS failed ({e}). Falling back to local Windows SAPI...")

            # 2. Resilient Fallback: Local Windows SAPI
            from app.audio.tts import _synthesize_local_sapi
            wav_path = mp3_path.replace(".mp3", ".wav")
            if _synthesize_local_sapi("Hello, I am Voro. This is how I sound.", wav_path):
                return wav_path

            raise RuntimeError("Both Edge TTS and local SAPI synthesis failed")

        def thread_task():
            try:
                fp = fetch_audio()
                from PySide6.QtCore import QMetaObject, Qt, Q_ARG
                QMetaObject.invokeMethod(self, "_play_test_audio", Qt.QueuedConnection, Q_ARG(str, fp))
            except Exception as e:
                logger.error(f"[settings] Test voice failed: {e}")
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._reset_test_voice_btn)

        threading.Thread(target=thread_task, daemon=True).start()

    @Slot(str)
    def _play_test_audio(self, filepath):
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
        from PySide6.QtCore import QUrl
        try:
            if not hasattr(self, '_test_player') or self._test_player is None:
                self._test_player = QMediaPlayer(self)
                self._test_audio = QAudioOutput(self)
                self._test_player.setAudioOutput(self._test_audio)
                self._test_player.mediaStatusChanged.connect(self._on_test_status)
                self._test_player.errorOccurred.connect(self._on_test_error)

            self._test_player.stop()

            # Apply output device
            if hasattr(self, 'tts_output_device_combo'):
                target_name = self.tts_output_device_combo.currentText().strip()
                if target_name == "Default System Device":
                    self._test_audio.setDevice(QMediaDevices.defaultAudioOutput())
                else:
                    for dev in QMediaDevices.audioOutputs():
                        if dev.description() == target_name:
                            self._test_audio.setDevice(dev)
                            break

            # Apply volume
            vol = self.tts_vol_slider.value() if hasattr(self, 'tts_vol_slider') else 100
            self._test_audio.setVolume(vol / 100.0)

            self._current_test_filepath = filepath
            self._test_player.setSource(QUrl.fromLocalFile(filepath))
            self._test_player.play()
        except Exception as e:
            logger.error(f"[settings] Error playing test audio: {e}")
            self._reset_test_voice_btn()

    def _on_test_status(self, status):
        from PySide6.QtMultimedia import QMediaPlayer
        if status in (QMediaPlayer.MediaStatus.EndOfMedia, QMediaPlayer.MediaStatus.InvalidMedia):
            if hasattr(self, '_test_watchdog') and self._test_watchdog:
                self._test_watchdog.stop()
            self._reset_test_voice_btn()
            # Clean up temp file
            if hasattr(self, '_current_test_filepath') and self._current_test_filepath:
                try:
                    if os.path.exists(self._current_test_filepath):
                        os.remove(self._current_test_filepath)
                except Exception:
                    pass

    def _on_test_error(self, error, error_string=""):
        logger.warning(f"[settings] Test audio error occurred: {error} ({error_string})")
        if hasattr(self, '_test_watchdog') and self._test_watchdog:
            self._test_watchdog.stop()
        self._reset_test_voice_btn()



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
        

    def _cleanup_audio(self):
        if hasattr(self, '_test_player') and self._test_player:
            try:
                self._test_player.stop()
            except Exception:
                pass
        if hasattr(self, '_test_watchdog') and self._test_watchdog:
            try:
                self._test_watchdog.stop()
            except Exception:
                pass

    def _save_settings_geometry(self):
        self._qsettings.setValue("settings_geometry", self.saveGeometry())

    def closeEvent(self, event):
        self._cleanup_audio()
        self._save_settings_geometry()
        super().closeEvent(event)

    def accept(self):
        self._cleanup_audio()
        self._save_settings_geometry()
        super().accept()

    def reject(self):
        self._cleanup_audio()
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
        os.environ["MUTE_USER_MIC"] = str(self.btn_mute_mic.isChecked())
        os.environ["MUTE_SYSTEM_AUDIO"] = str(self.btn_mute_sys.isChecked())
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
        if hasattr(self, 'auto_answer_hotkey_input'): set_key(self.env_path, "UI_AUTO_ANSWER_HOTKEY", self.auto_answer_hotkey_input.text().strip())
        if hasattr(self, 'manual_answer_hotkey_input'): set_key(self.env_path, "UI_MANUAL_ANSWER_HOTKEY", self.manual_answer_hotkey_input.text().strip())
        if hasattr(self, 'chk_auto_answer'):
            val = str(self.chk_auto_answer.isChecked())
            set_key(self.env_path, "UI_AUTO_ANSWER", val)
            os.environ["UI_AUTO_ANSWER"] = val
            self.config.ui_auto_answer = self.chk_auto_answer.isChecked()

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

        if hasattr(self, 'btn_tts_muted'):
            set_key(self.env_path, "UI_TTS_MUTED", str(self.btn_tts_muted.isChecked()))
            os.environ["UI_TTS_MUTED"] = str(self.btn_tts_muted.isChecked())

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
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        is_dark = self.theme.get('bg', '#1E1E1E') == '#1E1E1E'
        card_bg = "#252526" if is_dark else "#FFFFFF"
        border_col = "#383838" if is_dark else "#E2E8F0"
        text_primary = "#FFFFFF" if is_dark else "#0F172A"
        text_secondary = "#94A3B8" if is_dark else "#475569"
        accent = "#0078D7" if is_dark else "#0055A4"

        from app.core.version import APP_VERSION

        # Header Card: Current Installed Version
        header_card = QFrame()
        header_card.setStyleSheet(f"QFrame {{ background-color: {card_bg}; border: 1px solid {border_col}; border-radius: 8px; }}")
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(15, 12, 15, 12)

        v_lbl = QLabel(f"<span style='font-size: 14px; font-weight: bold; color: {text_primary};'>Current Installed Version:</span> <span style='font-size: 15px; color: {accent}; font-weight: bold;'>v{APP_VERSION}</span>")
        v_lbl.setStyleSheet("border: none; background: transparent;")
        h_layout.addWidget(v_lbl)
        h_layout.addStretch()

        status_badge = QLabel("Active Release")
        status_badge.setStyleSheet(f"background-color: {'#166534' if is_dark else '#DCFCE7'}; color: {'#4ADE80' if is_dark else '#15803D'}; font-weight: bold; font-size: 11px; padding: 4px 10px; border-radius: 10px; border: none;")
        h_layout.addWidget(status_badge)

        layout.addWidget(header_card)

        # Release Notes / What's New Container
        layout.addWidget(_make_section_header("What's New in This Release", self.theme))

        notes_scroll = QScrollArea()
        notes_scroll.setWidgetResizable(True)
        notes_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        notes_widget = QWidget()
        notes_layout = QVBoxLayout(notes_widget)
        notes_layout.setContentsMargins(16, 16, 16, 16)
        notes_widget.setStyleSheet(f"QWidget {{ background-color: {card_bg}; border: 1px solid {border_col}; border-radius: 8px; }}")

        self.lbl_release_notes = QLabel(
            f"<div style='line-height: 1.6; font-size: 13px; color: {text_primary};'>"
            f"<b style='font-size: 14px; color: {accent};'>Version {APP_VERSION} Highlights & Improvements:</b><br><br>"
            "• <b>Push-to-Answer & Auto-Answer Toggle:</b> Switch seamlessly between instant automatic answering (<code>⚡ Auto</code>) and manual push-to-answer (<code>⏸️ Manual</code>) with <code>Ctrl+Shift+U</code>.<br><br>"
            "• <b>Interview Question Distillation Engine:</b> In Manual Mode (<code>Ctrl+Enter</code>), Voro automatically filters out conversational chit-chat, greetings, and filler conversation from multiple turns of speech to distill and answer the real technical question directly.<br><br>"
            "• <b>Full-Duplex Speech & Instant Interruptibility:</b> Microphone capture remains active while Voro speaks, instantly halting TTS speech when you begin talking.<br><br>"
            "• <b>Hard Audio Muting & Queue Purging:</b> Immediately purges pending audio buffers and resets voice detection engines the moment user mic or system audio is muted.<br><br>"
            "• <b>Light & Dark Theme Visual Overhaul:</b> Complete high-contrast visual refresh across all message boxes, alert dialogs, and popups.<br><br>"
            "• <b>Voice Output Experimental Advisory:</b> Clear warning banners and device compatibility notices before activating Voro Voice.<br><br>"
            "• <b>Performance Optimizations:</b> Faster startup routines, resilient local SAPI fallback, and robust error recovery.<br>"
            "</div>"
        )
        self.lbl_release_notes.setWordWrap(True)
        self.lbl_release_notes.setStyleSheet("border: none; background: transparent;")
        notes_layout.addWidget(self.lbl_release_notes)
        notes_scroll.setWidget(notes_widget)
        layout.addWidget(notes_scroll)

        # Bottom section: Check for Updates button
        layout.addSpacing(10)
        self.btn_check_update = QPushButton("Check for Updates")
        self.btn_check_update.setCursor(Qt.PointingHandCursor)
        self.btn_check_update.setStyleSheet(f"QPushButton {{ background-color: {accent}; color: white; border: none; padding: 10px 20px; font-weight: bold; border-radius: 6px; font-size: 13px; }} QPushButton:hover {{ background-color: {'#0066CC' if is_dark else '#004080'}; }}")
        self.btn_check_update.clicked.connect(self._check_for_updates)
        layout.addWidget(self.btn_check_update)

        self.lbl_update_status = QLabel("")
        self.lbl_update_status.setAlignment(Qt.AlignCenter)
        self.lbl_update_status.setStyleSheet(f"color: {text_secondary}; font-size: 12px; border: none;")
        layout.addWidget(self.lbl_update_status)

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

        is_dark = self.theme.get('bg', '#1E1E1E') == '#1E1E1E'
        card_bg = "#252526" if is_dark else "#FFFFFF"
        border_col = "#383838" if is_dark else "#E2E8F0"
        text_primary = "#FFFFFF" if is_dark else "#0F172A"
        text_secondary = "#94A3B8" if is_dark else "#475569"
        accent = "#0078D7" if is_dark else "#0055A4"
        accent_hover = "#0066CC" if is_dark else "#004080"
        
        kbd_bg = "#2D3748" if is_dark else "#E2E8F0"
        kbd_fg = "#F8FAFC" if is_dark else "#0F172A"
        kbd_border = "#4A5568" if is_dark else "#CBD5E1"
        def _kbd(keys):
            return " + ".join([f"<kbd style='background-color: {kbd_bg}; color: {kbd_fg}; border: 1px solid {kbd_border}; border-radius: 4px; padding: 2px 7px; font-family: Consolas, monospace; font-size: 12px; font-weight: bold;'>{k.strip()}</kbd>" for k in keys.split("+")])

        # --- Dropdown 1: Setup Guide ---
        self.box_setup = CollapsibleBox("🚀 Quick Setup Guide (First-Time Setup)", parent=self, is_dark=is_dark)

        # Check Ollama installed status
        import shutil
        ollama_installed = False
        if shutil.which("ollama"):
            ollama_installed = True
        else:
            local_app_data = os.environ.get('LOCALAPPDATA', '')
            prog_files = os.environ.get('ProgramFiles', 'C:\\Program Files')
            if (os.path.exists(os.path.join(local_app_data, 'Programs', 'Ollama', 'ollama.exe')) or
                os.path.exists(os.path.join(prog_files, 'Ollama', 'ollama.exe'))):
                ollama_installed = True

        groq_key = (getattr(self.config, 'groq_api_key', '') or os.environ.get("GROQ_API_KEY", "")).strip()
        groq_configured = bool(groq_key and len(groq_key) > 10)

        # Step 1 Frame: Ollama
        step1_frame = QFrame()
        step1_frame.setStyleSheet(f"QFrame {{ background-color: {card_bg}; border: 1px solid {border_col}; border-radius: 6px; }}")
        s1_layout = QVBoxLayout(step1_frame)
        s1_layout.setContentsMargins(12, 12, 12, 12)
        s1_layout.setSpacing(8)

        s1_title = QLabel(f"<b style='font-size: 13px; color: {text_primary};'>Step 1 — Download & Install Ollama (AI Brain)</b>")
        s1_title.setStyleSheet("border: none; background: transparent;")
        s1_layout.addWidget(s1_title)

        s1_desc = QLabel(
            f"<div style='line-height: 1.6; font-size: 12px; color: {text_secondary};'>"
            "Ollama powers Voro's AI intelligence with high speed and zero cloud data leaks.<br><br>"
            "<b>Step-by-step instructions:</b><br>"
            "1. Click the button below to download the official installer (<code>OllamaSetup.exe</code>).<br>"
            "2. Run the installer and finish installing Ollama on your PC.<br>"
            "3. Open the Ollama application once from your Start Menu (you can log in or skip).<br>"
            "4. Close or minimize Ollama (it continues running quietly in your Windows taskbar tray).<br>"
            "5. Voro will automatically connect to your local Ollama AI engine!"
            "</div>"
        )
        s1_desc.setWordWrap(True)
        s1_desc.setStyleSheet("border: none; background: transparent;")
        s1_layout.addWidget(s1_desc)

        self.btn_s1 = QPushButton()
        self.btn_s1.setCursor(Qt.PointingHandCursor)
        self.btn_s1.setFixedWidth(280)
        if ollama_installed:
            self.btn_s1.setText("✅ Step 1 Completed (Ollama Installed)")
            self.btn_s1.setStyleSheet(f"QPushButton {{ background-color: {'#166534' if is_dark else '#DCFCE7'}; color: {'#4ADE80' if is_dark else '#15803D'}; border: 1px solid {'#22C55E' if is_dark else '#86EFAC'}; padding: 8px 16px; border-radius: 5px; font-weight: bold; font-size: 12px; }} QPushButton:hover {{ background-color: {'#15803D' if is_dark else '#BBF7D0'}; }}")
        else:
            self.btn_s1.setText("📥 Step 1 — Download Ollama (Windows)")
            self.btn_s1.setStyleSheet(f"QPushButton {{ background-color: {accent}; color: white; border: none; padding: 8px 16px; border-radius: 5px; font-weight: bold; font-size: 12px; }} QPushButton:hover {{ background-color: {accent_hover}; }}")
        self.btn_s1.clicked.connect(self._open_setup_browser)
        s1_layout.addWidget(self.btn_s1)

        self.box_setup.addWidget(step1_frame)

        # Step 2 Frame: Groq API Key
        step2_frame = QFrame()
        step2_frame.setStyleSheet(f"QFrame {{ background-color: {card_bg}; border: 1px solid {border_col}; border-radius: 6px; }}")
        s2_layout = QVBoxLayout(step2_frame)
        s2_layout.setContentsMargins(12, 12, 12, 12)
        s2_layout.setSpacing(8)

        s2_title = QLabel(f"<b style='font-size: 13px; color: {text_primary};'>Step 2 — Get Free Groq API Key (Ultra-Fast Speech Recognition)</b>")
        s2_title.setStyleSheet("border: none; background: transparent;")
        s2_layout.addWidget(s2_title)

        s2_desc = QLabel(
            f"<div style='line-height: 1.6; font-size: 12px; color: {text_secondary};'>"
            "To get near-instant voice transcription (200ms) for interviews, you dont need to pay Groq.<br><br>"
            "<b>Step-by-step instructions:</b><br>"
            "1. Click the button below to open the official Groq Console website.<br>"
            "2. Sign up or log in (100% free with your Google or GitHub account).<br>"
            "3. Click <b>'Create API Key'</b>.<br>"
            "4. Set the key name to <b>VORO</b> and expiration to <b>No Expiration</b>.<br>"
            "5. Copy your generated key (starts with <code>gsk_...</code>).<br>"
            "6. In Voro, go to the <b>Audio</b> settings tab, paste it into the <b>Groq API Key</b> field, and click <b>Save & Restart</b>!"
            "</div>"
        )
        s2_desc.setWordWrap(True)
        s2_desc.setStyleSheet("border: none; background: transparent;")
        s2_layout.addWidget(s2_desc)

        self.btn_s2 = QPushButton()
        self.btn_s2.setCursor(Qt.PointingHandCursor)
        self.btn_s2.setFixedWidth(280)
        if groq_configured:
            self.btn_s2.setText("✅ Step 2 Completed (Groq Key Active)")
            self.btn_s2.setStyleSheet(f"QPushButton {{ background-color: {'#166534' if is_dark else '#DCFCE7'}; color: {'#4ADE80' if is_dark else '#15803D'}; border: 1px solid {'#22C55E' if is_dark else '#86EFAC'}; padding: 8px 16px; border-radius: 5px; font-weight: bold; font-size: 12px; }} QPushButton:hover {{ background-color: {'#15803D' if is_dark else '#BBF7D0'}; }}")
        else:
            self.btn_s2.setText("⚡ Step 2 — Get Free Groq API Key")
            self.btn_s2.setStyleSheet(f"QPushButton {{ background-color: {'#16A34A' if is_dark else '#15803D'}; color: white; border: none; padding: 8px 16px; border-radius: 5px; font-weight: bold; font-size: 12px; }} QPushButton:hover {{ background-color: {'#15803D' if is_dark else '#166534'}; }}")
        self.btn_s2.clicked.connect(self._open_groq_console)
        s2_layout.addWidget(self.btn_s2)

        self.box_setup.addWidget(step2_frame)

        # Optional Offline STT Note
        s3_note = QLabel(
            "<b>Optional — Offline Voice Fallback:</b><br>"
            "If your internet drops during a call, Voro can fall back to a local offline Whisper model. "
            "Go to the <b>Audio</b> tab and click 'Download STT Model' to store it permanently on your device.<br><br>"
            "<i>Note: Voro's Brain and Screen Vision systems are entirely managed. Once Steps 1 & 2 are complete, you are 100% interview-ready!</i>"
        )
        s3_note.setWordWrap(True)
        s3_note.setStyleSheet(f"font-size: 12px; color: {text_secondary}; line-height: 1.4; padding: 4px;")
        self.box_setup.addWidget(s3_note)

        content_layout.addWidget(self.box_setup)

        # --- Dropdown 2: Controls & Shortcuts ---
        box_help = CollapsibleBox("⌨️ Voro Controls & Shortcut Keys", parent=self, is_dark=is_dark)

        hk_global = self.config.ui_global_hotkey
        hk_hint = self.config.ui_hint_hotkey
        hk_snip = self.config.ui_snip_hotkey
        hk_stealth = self.config.ui_stealth_hotkey
        hk_stop = self.config.ui_stop_hotkey
        hk_clear = self.config.ui_clear_session_hotkey
        hk_mute_mic = self.config.ui_mute_mic_hotkey
        hk_mute_sys = self.config.ui_mute_sys_hotkey
        hk_mute_tts = self.config.ui_tts_mute_hotkey
        hk_taskbar = self.config.ui_taskbar_hotkey
        hk_tray = self.config.ui_toggle_tray_hotkey
        hk_cycle = self.config.ui_cycle_mode_hotkey
        hk_auto_ans = getattr(self.config, 'ui_auto_answer_hotkey', 'ctrl+shift+u')
        hk_manual_ans = getattr(self.config, 'ui_manual_answer_hotkey', 'ctrl+enter')
        hk_max = getattr(self.config, 'ui_maximize_hotkey', 'F11')
        hk_qp1 = self.config.ui_quick_prompt_1_hotkey
        hk_qp2 = self.config.ui_quick_prompt_2_hotkey
        hk_qp3 = self.config.ui_quick_prompt_3_hotkey

        lbl_shortcuts = QLabel(
            f"<div style='line-height: 1.8; font-size: 13px; color: {text_primary};'>"
            "<i>(All hotkeys are fully customizable in the <b>Interface</b> settings tab)</i><br><br>"
            f"<b style='font-size: 14px; color: {accent};'>1. Answering & Live Modes:</b><br>"
            f"• {_kbd(hk_auto_ans)} : <b>Toggle Auto/Manual Answer Mode</b> (Switch between <code>⚡ Auto</code> and <code>⏸️ Manual</code>)<br>"
            f"• {_kbd(hk_manual_ans)} : <b>Trigger Manual Answer</b> (Instantly distill recent conversation & answer core question)<br>"
            f"• {_kbd(hk_global)} : <b>Global Summon</b> (Wake Voro up and start listening)<br>"
            f"• {_kbd(hk_hint)} : <b>Toggle Hint Mode</b> (Answers appear silently in the text box without voice)<br>"
            f"• {_kbd(hk_snip)} : <b>Toggle Snip Mode</b> (Drag and select screen area for OCR & coding prompts)<br>"
            f"• {_kbd(hk_qp1)} / {_kbd(hk_qp2)} / {_kbd(hk_qp3)} : <b>Quick Prompts 1, 2, 3</b> (Solve screen question, explain code, summarize)<br><br>"
            f"<b style='font-size: 14px; color: {accent};'>2. Audio & Privacy Controls:</b><br>"
            f"• {_kbd(hk_stealth)} : <b>Toggle Stealth Mode</b> (100% invisible to Zoom, Teams, Meet, OBS screenshares & screenshots)<br>"
            f"• {_kbd(hk_mute_mic)} : <b>Mute User Microphone</b> (Hard mute your mic input)<br>"
            f"• {_kbd(hk_mute_sys)} : <b>Mute System Audio Capture</b> (Hard mute interviewer voice capture)<br>"
            f"• {_kbd(hk_mute_tts)} : <b>Mute Voro Voice</b> (Mute AI spoken speech output)<br><br>"
            f"<b style='font-size: 14px; color: {accent};'>3. Session & Window Controls:</b><br>"
            f"• {_kbd(hk_stop)} : <b>Stop Current Task</b> (Instantly halts AI generation and voice playback)<br>"
            f"• {_kbd(hk_clear)} : <b>Clear Session</b> (Wipe conversation memory for a fresh topic)<br>"
            f"• {_kbd(hk_taskbar)} : <b>Toggle Taskbar Visibility</b> (Hide or show Voro in Windows taskbar)<br>"
            f"• {_kbd(hk_tray)} : <b>Toggle System Tray Icon</b> (Show or hide tray icon)<br>"
            f"• {_kbd(hk_cycle)} : <b>Cycle Interface Mode</b> (Switch between Standard, Compact, and Minimal views)<br>"
            f"• {_kbd(hk_max)} : <b>Maximize / Restore Window</b><br><br>"
            "<b>💡 Pro Tip — Occupancy Slider:</b><br>"
            "Use the <b>Occupancy</b> slider on Voro's main top bar to adjust transparency. You can slide it down to make Voro nearly transparent and completely discreet during an interview!"
            "</div>"
        )
        lbl_shortcuts.setWordWrap(True)
        lbl_shortcuts.setStyleSheet("border: none; background: transparent;")
        box_help.addWidget(lbl_shortcuts)
        content_layout.addWidget(box_help)

        # --- Dropdown 3: Complete User Manual & Feature Guide (NEW) ---
        box_manual = CollapsibleBox("📘 Complete User Manual & Feature Guide", parent=self, is_dark=is_dark)

        # Real Interview Best Practices Callout Card
        rules_frame = QFrame()
        rules_bg = "#2D2206" if is_dark else "#FFF8E1"
        rules_border = "#B27B00" if is_dark else "#FFE082"
        rules_text = "#FFE082" if is_dark else "#8C5400"
        rules_frame.setStyleSheet(f"QFrame {{ background-color: {rules_bg}; border: 1px solid {rules_border}; border-radius: 6px; padding: 10px; }}")
        rf_layout = QVBoxLayout(rules_frame)
        rf_layout.setContentsMargins(10, 8, 10, 8)
        rf_layout.setSpacing(6)

        rf_title = QLabel("<b>🌟 Real Interview Golden Rules (Must-Know Settings):</b>")
        rf_title.setStyleSheet(f"font-size: 13px; color: {rules_text}; font-weight: bold; border: none; background: transparent;")
        rf_layout.addWidget(rf_title)

        rf_text = QLabel(
            "• <b>Rule 1: Keep System Audio Capture ON (🎧 Green)</b> — This allows Voro to hear what the interviewer is asking through your headphones/speakers.<br>"
            "• <b>Rule 2: Keep Vision System Enabled</b> — When doing LeetCode, system design, or reviewing slides, Vision ensures Voro reads the code or problem directly.<br>"
            "• <b>Rule 3: Use Manual Mode (Ctrl+Enter)</b> — If the interviewer pauses frequently or engages in small talk, switch to <code>⏸️ Manual</code> mode so Voro only answers when you trigger it.<br>"
            "• <b>Rule 4: Turn Stealth Mode ON (Ctrl+Shift+G)</b> — Always enable Stealth Mode before sharing your screen so Voro remains 100% invisible to the interviewer."
        )
        rf_text.setWordWrap(True)
        rf_text.setStyleSheet(f"font-size: 12px; color: {rules_text}; line-height: 1.5; border: none; background: transparent;")
        rf_layout.addWidget(rf_text)
        box_manual.addWidget(rules_frame)

        # 100% Unlimited & Privacy Guarantee Banner
        priv_frame = QFrame()
        priv_bg = "#0D2818" if is_dark else "#F0FDF4"
        priv_border = "#166534" if is_dark else "#BBF7D0"
        priv_text = "#4ADE80" if is_dark else "#166534"
        priv_frame.setStyleSheet(f"QFrame {{ background-color: {priv_bg}; border: 1px solid {priv_border}; border-radius: 6px; padding: 10px; }}")
        pf_layout = QVBoxLayout(priv_frame)
        pf_layout.setContentsMargins(10, 8, 10, 8)
        pf_layout.setSpacing(6)

        pf_title = QLabel("<b>🛡️ 100% Free, Unlimited & Zero-Data-Logging Guarantee:</b>")
        pf_title.setStyleSheet(f"font-size: 13px; color: {priv_text}; font-weight: bold; border: none; background: transparent;")
        pf_layout.addWidget(pf_title)

        pf_text = QLabel(
            "• <b>No Hidden Fees / 100% Unlimited:</b> Once activated with your license key, Voro is completely yours. There are no monthly fees, no credit limits, and no question caps.<br>"
            "• <b>100% Local Privacy:</b> Norvi Agency NEVER records, stores, or transmits your audio, screen captures, resumes, or interview questions to any Norvi servers. Everything runs strictly locally on your machine and private endpoints."
        )
        pf_text.setWordWrap(True)
        pf_text.setStyleSheet(f"font-size: 12px; color: {priv_text}; line-height: 1.5; border: none; background: transparent;")
        pf_layout.addWidget(pf_text)
        box_manual.addWidget(priv_frame)

        # Deep Feature Explanations
        manual_details = QLabel(
            f"<div style='line-height: 1.7; font-size: 13px; color: {text_primary};'>"
            f"<b style='font-size: 14px; color: {accent};'>1. AI Personality & Tone Selection:</b><br>"
            "Customize the exact answering style to match the interview format (in <b>Settings ➔ General</b>):<br>"
            "• <i>Conversational (Script):</i> Natural spoken interview style; sounds like you are speaking live.<br>"
            "• <i>Conversational (Hinglish):</i> Natural bilingual tech interview tone; seamlessly blends English tech concepts with conversational flow.<br>"
            "• <i>Direct & Technical:</i> Concise bullet points, architectural trade-offs, and clean code blocks.<br>"
            "• <i>Supportive & Encouraging:</i> Calm, structured, step-by-step guidance for complex algorithmic challenges.<br><br>"
            f"<b style='font-size: 14px; color: {accent};'>2. Offline STT Model vs Groq STT:</b><br>"
            "• <b>Online Groq STT (Recommended):</b> Runs Whisper in under 200 milliseconds in the cloud. Essential for live conversational pacing.<br>"
            "• <b>Offline Faster-Whisper:</b> Runs 100% locally on your computer's CPU/GPU. Zero internet required; ideal as a robust offline fallback.<br><br>"
            f"<b style='font-size: 14px; color: {accent};'>3. Stealth Mode (Zero Detection Architecture):</b><br>"
            "Uses Windows native <code>SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)</code> to make Voro completely invisible to Zoom, Microsoft Teams, Google Meet, OBS Studio, Discord, Slack, and screenshot utilities. It also removes Voro from the Windows Task Manager Applications list.<br><br>"
            f"<b style='font-size: 14px; color: {accent};'>4. Vision System & Snip Mode:</b><br>"
            "Real-time screen analysis with high-accuracy stealth OCR. Automatically reads code editors, LeetCode / HackerRank problems, architectural diagrams, and browser tabs. Snip Mode (<code>Ctrl+Shift+P</code>) allows pinpoint region selection.<br><br>"
            f"<b style='font-size: 14px; color: {accent};'>5. Dual-Channel Audio Subsystem & Diarization:</b><br>"
            "Processes your microphone and system loopback audio separately. Intelligent diarization tags each speaker automatically: <code>[Interviewer]</code> vs <code>[You]</code>, ensuring the AI always knows who is asking.<br><br>"
            f"<b style='font-size: 14px; color: {accent};'>6. Candidate Resume Profile & Target Company Context:</b><br>"
            "• <b>Profile Tab:</b> Paste or import your resume so Voro tailors answers to your real career accomplishments, projects, and tech stack.<br>"
            "• <b>Company Tab:</b> Add company details and role requirements so answers reflect their specific engineering culture and values.<br><br>"
            f"<b style='font-size: 14px; color: {accent};'>7. Auto-Answer vs Push-to-Answer Mode:</b><br>"
            "• <b>Auto Mode (<code>⚡ Auto</code>):</b> Voro answers automatically as soon as the interviewer pauses.<br>"
            "• <b>Manual Mode (<code>⏸️ Manual</code>):</b> Voro listens and transcribes silently in the background. Press <code>Ctrl+Enter</code> or click <code>Answer ↵</code> when you want an answer; Voro automatically filters out conversational small talk and answers the real technical question.<br>"
            "</div>"
        )
        manual_details.setWordWrap(True)
        manual_details.setStyleSheet("border: none; background: transparent; padding-top: 5px;")
        box_manual.addWidget(manual_details)
        content_layout.addWidget(box_manual)

        # --- Dropdown 4: Support & Logs ---
        box_support = CollapsibleBox("🛠️ Support & Logs", parent=self, is_dark=is_dark)

        support_link_col = "#38BDF8" if is_dark else "#0055A4"
        support_lbl = QLabel(
            f"<div style='line-height: 1.6; font-size: 13px; color: {text_primary};'>"
            "If you encounter any issues, need setup guidance, or have questions, our dedicated engineering team is here to assist you.<br><br>"
            f"<b>📱 Official WhatsApp Support:</b> <a href='https://wa.me/919893534314?text=Hello%20Norvi%20Support%2C%20I%20need%20help%20with%20Voro' style='color:{support_link_col}; text-decoration:none; font-weight:bold;'>+91 9893534314</a><br>"
            f"<b>🌐 Website Support:</b> <a href='https://nor-vi.in/contact/' style='color:{support_link_col}; text-decoration:none;'>https://nor-vi.in/contact/</a><br>"
            "</div>"
        )
        support_lbl.setWordWrap(True)
        support_lbl.setOpenExternalLinks(True)
        support_lbl.setStyleSheet("border: none; background: transparent;")
        box_support.addWidget(support_lbl)

        # WhatsApp Direct Action Button
        btn_wa = QPushButton("💬 Chat on WhatsApp (+91 9893534314)")
        btn_wa.setCursor(Qt.PointingHandCursor)
        btn_wa.setStyleSheet("QPushButton { background-color: #25D366; color: white; border: none; padding: 9px 18px; border-radius: 6px; font-weight: bold; font-size: 13px; } QPushButton:hover { background-color: #1EBE5D; }")
        btn_wa.clicked.connect(self._open_whatsapp_support)
        box_support.addWidget(btn_wa)

        box_support.addWidget(QLabel("<b style='font-size: 12px; color: #888;'>Diagnostics & Troubleshooting Logs:</b>"))

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

    def _open_groq_console(self):
        import webbrowser
        webbrowser.open("https://console.groq.com/keys")

    def _open_whatsapp_support(self):
        import webbrowser
        webbrowser.open("https://wa.me/919893534314?text=Hello%20Norvi%20Support%2C%20I%20need%20help%20with%20Voro")

    def _open_log_folder(self):
        import os
        appdata = os.getenv("APPDATA", os.path.expanduser("~"))
        log_dir = os.path.join(appdata, "Norvi", "Voro", "logs")
        os.makedirs(log_dir, exist_ok=True)
        os.startfile(log_dir)

    def _check_for_updates(self):
        self.btn_check_update.setText("Checking for updates...")
        self.btn_check_update.setEnabled(False)
        self.lbl_update_status.setText("Connecting to GitHub release server...")
        from app.core.updater import Updater
        self._temp_updater = Updater()
        self._temp_updater.update_available.connect(self._on_update_found)
        self._temp_updater.no_update.connect(self._on_no_update)
        self._temp_updater.check_error.connect(self._on_update_error)
        self._temp_updater.check_for_updates()

    def _on_update_found(self, version, notes, url):
        self.btn_check_update.setText("Check for Updates")
        self.btn_check_update.setEnabled(True)
        self.lbl_update_status.setText(f"Update available: v{version}")
        if notes and notes.strip():
            self.lbl_release_notes.setText(
                f"<div style='line-height: 1.6; font-size: 13px;'>"
                f"<b style='font-size: 14px; color: #0078D7;'>New Version {version} Available:</b><br><br>"
                f"{notes.replace(chr(10), '<br>')}"
                f"</div>"
            )
        from PySide6.QtWidgets import QMessageBox
        from app.ui.theme import style_message_box
        box = QMessageBox(self)
        style_message_box(box, theme_mode=getattr(self.config, 'ui_theme_mode', 'system'), parent=self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Update Voro")
        box.setText(f"<b>Version {version} is available!</b><br><br><b>Release Notes:</b><br>{notes}<br><br>Do you want to download and install it now?")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        reply = box.exec() if not os.environ.get("PYTEST_CURRENT_TEST") else QMessageBox.StandardButton.No
        if reply == QMessageBox.StandardButton.Yes:
            self.btn_check_update.setText("Downloading...")
            self.btn_check_update.setEnabled(False)
            self._temp_updater.download_progress.connect(lambda p: self.btn_check_update.setText(f"D/L: {p}%"))
            self._temp_updater.download_error.connect(lambda e: self.btn_check_update.setText("Failed"))
            self._temp_updater.download_and_install(url)

    def _on_no_update(self):
        self.btn_check_update.setText("Check for Updates")
        self.btn_check_update.setEnabled(True)
        self.lbl_update_status.setText("✓ You are running the latest version of Voro.")
        from PySide6.QtWidgets import QMessageBox
        from app.ui.theme import style_message_box
        box = QMessageBox(self)
        style_message_box(box, theme_mode=getattr(self.config, 'ui_theme_mode', 'system'), parent=self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Up to Date")
        box.setText("<b>You are running the latest version of Voro.</b>")
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            box.exec()

    def _on_update_error(self, err):
        self.btn_check_update.setText("Check for Updates")
        self.btn_check_update.setEnabled(True)
        self.lbl_update_status.setText(f"Check failed: {err}")
        from PySide6.QtWidgets import QMessageBox
        from app.ui.theme import style_message_box
        box = QMessageBox(self)
        style_message_box(box, theme_mode=getattr(self.config, 'ui_theme_mode', 'system'), parent=self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Update Failed")
        box.setText(f"<b>Could not check for updates:</b><br><br>{err}")
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            box.exec()


    
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
        import json, base64, shutil, time as _time
        page = QWidget()
        layout = QVBoxLayout(page)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        
        header_row = QHBoxLayout()
        logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "norvi_logo.png"))
        if not os.path.exists(logo_path):
            try:
                import sys
                logo_path = os.path.join(sys._MEIPASS, "norvi_logo.png")
            except Exception:
                pass
        if os.path.exists(logo_path):
            from PySide6.QtGui import QPixmap
            logo_pix = QPixmap(logo_path)
            if not logo_pix.isNull():
                h_logo = QLabel()
                h_logo.setPixmap(logo_pix.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                header_row.addWidget(h_logo)
        header_title = QLabel("<h2>Norvi Agent Credentials</h2>")
        header_row.addWidget(header_title)
        header_row.addStretch()
        inner_layout.addLayout(header_row)
        
        is_dark = self.theme.get('bg', '#1E1E1E') == '#1E1E1E'
        text_secondary = "#94A3B8" if is_dark else "#475569"
        accent = "#0078D7" if is_dark else "#0055A4"
        accent_hover = "#0066CC" if is_dark else "#004080"

        # --- First time setup (Ollama & Groq Setup Guidance) ---
        setup_lbl = QLabel("First-Time Setup: Go to <b>Help ➔ Quick Setup Guide</b> to complete Step 1 (Ollama AI Brain) and Step 2 (Groq Speech Key).")
        setup_lbl.setWordWrap(True)
        setup_lbl.setStyleSheet(f"color: {text_secondary}; font-size: 12px; margin-top: 10px; line-height: 1.4;")
        inner_layout.addWidget(setup_lbl)
        
        self.btn_setup = QPushButton("Setup")
        self.btn_setup.setCursor(Qt.PointingHandCursor)
        self.btn_setup.setFixedWidth(260)
        
        # Check if Ollama is already installed
        ollama_installed = False
        if shutil.which("ollama"):
            ollama_installed = True
        else:
            local_app_data = os.environ.get('LOCALAPPDATA', '')
            prog_files = os.environ.get('ProgramFiles', 'C:\\Program Files')
            if (os.path.exists(os.path.join(local_app_data, 'Programs', 'Ollama', 'ollama.exe')) or
                os.path.exists(os.path.join(prog_files, 'Ollama', 'ollama.exe'))):
                ollama_installed = True

        groq_key = (getattr(self.config, 'groq_api_key', '') or os.environ.get("GROQ_API_KEY", "")).strip()
        groq_configured = bool(groq_key and len(groq_key) > 10)
                
        if ollama_installed and groq_configured:
            self.btn_setup.setText("✅ Setup Completed")
            self.btn_setup.setEnabled(False)
            self.btn_setup.setStyleSheet(f"QPushButton {{ background-color: {'#166534' if is_dark else '#DCFCE7'}; color: {'#4ADE80' if is_dark else '#15803D'}; border: 1px solid {'#22C55E' if is_dark else '#86EFAC'}; border-radius: 5px; font-weight: bold; font-size: 12px; padding: 7px 14px; }}")
        elif ollama_installed and not groq_configured:
            self.btn_setup.setText("⚠️ Step 1 Done — Finish Step 2")
            self.btn_setup.setStyleSheet(f"QPushButton {{ background-color: {'#B45309' if is_dark else '#FEF3C7'}; color: {'#FCD34D' if is_dark else '#92400E'}; border: 1px solid {'#F59E0B' if is_dark else '#FCD34D'}; border-radius: 5px; font-weight: bold; font-size: 12px; padding: 7px 14px; }} QPushButton:hover {{ background-color: {'#92400E' if is_dark else '#FDE68A'}; }}")
            self.btn_setup.clicked.connect(self._navigate_to_setup)
        else:
            self.btn_setup.setText("🚀 Start Setup (Help ➔ Setup)")
            self.btn_setup.setStyleSheet(f"QPushButton {{ background-color: {accent}; color: white; border: none; border-radius: 5px; font-weight: bold; font-size: 12px; padding: 7px 14px; }} QPushButton:hover {{ background-color: {accent_hover}; }}")
            self.btn_setup.clicked.connect(self._navigate_to_setup)
            
        inner_layout.addWidget(self.btn_setup)
        
        inner_layout.addSpacing(20)
        
        lease_file = os.path.join(os.path.expanduser("~"), ".norvi_voro_lease")
        
        license_id = ""
        device_id = ""
        product = ""
        status = "Not Activated"
        
        if os.path.exists(lease_file):
            try:
                with open(lease_file, "r") as f:
                    data = json.load(f)
                token = data.get("token", "")
                expires_at = data.get("expires_at", 0)
                plan_expires_at = data.get("plan_expires_at")
                if token:
                    parts = token.split(".")
                    if len(parts) >= 2:
                        payload_b64 = parts[1]
                        payload_b64 += "=" * (-len(payload_b64) % 4)
                        decoded = json.loads(base64.b64decode(payload_b64).decode())
                        license_id = decoded.get("license_id", "")
                        device_id = decoded.get("device_id", "")
                        product = decoded.get("product", "voro").capitalize()

                import datetime
                if plan_expires_at:
                    if isinstance(plan_expires_at, (int, float)):
                        status = "Active" if _time.time() < plan_expires_at else "Expired"
                    elif isinstance(plan_expires_at, str):
                        try:
                            clean_iso = plan_expires_at.replace("Z", "+00:00")
                            exp_dt = datetime.datetime.fromisoformat(clean_iso).astimezone()
                            status = "Active" if _time.time() < exp_dt.timestamp() else "Expired"
                        except Exception:
                            status = "Active"
                elif plan_expires_at is None and ("plan_expires_at" in data or license_id):
                    status = "Active"
                elif expires_at:
                    status = "Active" if _time.time() < expires_at else "Expired"
            except Exception as e:
                status = f"Error: {e}"
        
        from PySide6.QtWidgets import QFormLayout
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setVerticalSpacing(12)
        
        is_dark = self.theme.get('bg', '#1E1E1E') == '#1E1E1E'
        ro_bg = "#252525" if is_dark else "#FFFFFF"
        ro_fg = "#E0E0E0" if is_dark else "#1A1A1A"
        ro_border = "#444444" if is_dark else "#D0D0D0"

        def _ro_field(val):
            f = QLineEdit()
            f.setText(val)
            f.setReadOnly(True)
            f.setStyleSheet(f"background: {ro_bg}; color: {ro_fg}; border: 1px solid {ro_border}; border-radius: 4px; padding: 4px 8px;")
            return f
        
        form.addRow("Status:", _ro_field(status))
        form.addRow("Product:", _ro_field(product or "Voro"))
        form.addRow("License ID:", _ro_field(license_id or "Not found"))
        form.addRow("Device ID:", _ro_field(device_id or "Not found"))
        
        inner_layout.addLayout(form)
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self.pages.addWidget(page)

