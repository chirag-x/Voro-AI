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

class SettingsDialog(QDialog):
    def __init__(self, context_manager: ContextManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Voro Settings")
        self.resize(650, 500)
        
        self.config = load_config()
        self.context_manager = context_manager
        self.env_path = os.path.join(os.getcwd(), ".env")
        
        # Auto-detect Windows theme
        from app.ui.theme import get_theme_colors
        self.theme = get_theme_colors(self.config.ui_theme_mode)
        
        # Modern Settings QSS
        bg_main = self.theme['bg']
        bg_card = "#222" if self.config.ui_theme_mode == 'dark' else "#F0F0F0"
        bg_card_hover = "#2A2A2A" if self.config.ui_theme_mode == 'dark' else "#E8E8E8"
        text_col = self.theme['base_text']
        accent = "#0055A4"
        
        modern_qss = f"""
        QDialog {{
            background-color: {bg_main};
            color: {text_col};
            font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            font-size: 13px;
        }}
        QListWidget {{
            background-color: {bg_main};
            border: none;
            outline: none;
            padding: 10px 5px;
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
            border: 1px solid #333;
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
            background-color: #333;
            color: white;
            border-radius: 6px;
            padding: 6px 12px;
            border: 1px solid #555;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: #444;
            border: 1px solid {accent};
        }}
        QPushButton.primary {{
            background-color: {accent};
            border: none;
        }}
        QPushButton.primary:hover {{
            background-color: #0066CC;
        }}
        QLineEdit, QComboBox {{
            background-color: #1A1A1A;
            border: 1px solid #444;
            border-radius: 4px;
            padding: 5px;
            color: {text_col};
        }}
        QLineEdit:focus, QComboBox:focus {{
            border: 1px solid {accent};
        }}
        QCheckBox::indicator {{
            width: 32px;
            height: 18px;
            border-radius: 9px;
            border: 1px solid #666;
            background-color: #333;
        }}
        QCheckBox::indicator:checked {{
            background-color: {accent};
            border: 1px solid {accent};
            image: none; /* Add custom checked rendering later or keep pure color */
        }}
        QCheckBox::indicator:unchecked:hover {{
            background-color: #444;
        }}
        QSlider::groove:horizontal {{
            height: 6px;
            background: #444;
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
        """
        self.setStyleSheet(modern_qss)
        
        # Main Layout: Sidebar + Stacked Widget
        outer_layout = QHBoxLayout(self)
        
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(150)
        self.sidebar.addItems(["Activation", "Window", "Audio", "Shortcuts", "Profile", "Company Info", "Other"])
        self.sidebar.currentRowChanged.connect(self.change_page)
        outer_layout.addWidget(self.sidebar)
        
        right_layout = QVBoxLayout()
        self.pages = QStackedWidget()
        right_layout.addWidget(self.pages)
        
        # Setup Pages
        self.setup_activation_page()
        self.setup_window_page()
        self.setup_audio_page()
        self.setup_shortcuts_page()
        self.setup_profile_page()
        self.setup_company_page()
        self.setup_other_page()
        
        # Initialize UI fields with current context (must happen after all pages exist)
        self.load_profile_fields(self.context_manager.active_profile_name)
        self._last_selected_profile = self.context_manager.active_profile_name
        
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
        
        # Apply theme-aware styling to dialog
        self.setStyleSheet(
            f"background-color: {self.theme['bg']};"
            f"color: {self.theme['base_text']};"
            "QListWidget::item:selected { background-color: #0055A4; color: white; }"
        )
        self._apply_privacy_flag()
        
    def change_page(self, index):
        self.pages.setCurrentIndex(index)
        



    def setup_activation_page(self):
        page = QWidget()
        main_layout = QVBoxLayout(page)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        inner = QWidget()
        layout = QVBoxLayout(inner)
        
        # Top Mode Selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("<b>Activation Mode:</b>"))
        self.mode_dropdown = QComboBox()
        self.mode_dropdown.addItems([
            "Premium Activation (Paid AI)",
            "Basic Activation (Free AI)",
            "Free Local Activation (Ollama)"
        ])
        mode_layout.addWidget(self.mode_dropdown)
        layout.addLayout(mode_layout)
        
        layout.addWidget(QLabel("<small><i>Voro will ONLY use the mode selected above.</i></small>"))
        
        from PySide6.QtWidgets import QFrame
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        
        # -----------------------------------------------------
        # 1. Premium Page
        # -----------------------------------------------------
        page_premium = QWidget()
        premium_layout = QVBoxLayout(page_premium)
        premium_layout.setContentsMargins(0, 0, 0, 0)
        
        premium_layout.addWidget(QLabel("Premium API Key (OpenRouter):"))
        self.premium_key_input = QLineEdit()
        self.premium_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.premium_key_input.setText(getattr(self.config, 'premium_api_key', ''))
        premium_layout.addWidget(self.premium_key_input)
        
        premium_layout.addWidget(QLabel("Model Name (e.g. openai/gpt-4o, anthropic/claude-3.5-sonnet):"))
        self.premium_model_input = QLineEdit()
        self.premium_model_input.setText(getattr(self.config, 'premium_model', 'openai/gpt-4o'))
        premium_layout.addWidget(self.premium_model_input)
        
        self.btn_validate_premium = QPushButton("Validate Premium Key & Model")
        self.btn_validate_premium.clicked.connect(self._validate_premium)
        premium_layout.addWidget(self.btn_validate_premium)
        
        premium_layout.addStretch()
        self.stack.addWidget(page_premium)
        
        # -----------------------------------------------------
        # 2. Basic Page
        # -----------------------------------------------------
        page_basic = QWidget()
        basic_layout = QVBoxLayout(page_basic)
        basic_layout.setContentsMargins(0, 0, 0, 0)
        
        basic_layout.addWidget(QLabel("OpenRouter API Key:"))
        key_layout = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        if self.config.openrouter_api_key:
            self.key_input.setText(self.config.openrouter_api_key)
        key_layout.addWidget(self.key_input)
        
        if not getattr(sys, 'frozen', False):
            self.btn_show_key = QPushButton("Show Key")
            self.btn_show_key.setCheckable(True)
            self.btn_show_key.toggled.connect(self.toggle_key_visibility)
            key_layout.addWidget(self.btn_show_key)
        basic_layout.addLayout(key_layout)
        
        basic_layout.addWidget(QLabel("Activation Models:"))
        self.model_inputs = []
        self.model_status_labels = []
        
        models = [
            self.config.openrouter_model,
            self.config.openrouter_model_2,
            self.config.openrouter_model_3,
            self.config.openrouter_model_4,
            self.config.openrouter_model_5
        ]
        
        for i, val in enumerate(models):
            h = QHBoxLayout()
            lbl = QLabel(f"Model {i+1}:")
            lbl.setFixedWidth(60)
            le = QLineEdit(val)
            self.model_inputs.append(le)
            status_lbl = QLabel("")
            status_lbl.setFixedWidth(30)
            self.model_status_labels.append(status_lbl)
            
            h.addWidget(lbl)
            h.addWidget(le)
            h.addWidget(status_lbl)
            basic_layout.addLayout(h)
            
        self.btn_validate = QPushButton("Validate Key & Models")
        self.btn_validate.clicked.connect(self.validate_models)
        basic_layout.addWidget(self.btn_validate)
        
        active_model_layout = QHBoxLayout()
        active_model_layout.addWidget(QLabel("Active Model:"))
        self.active_model_combo = QComboBox()
        self.active_model_combo.addItems([self.config.openrouter_model, self.config.openrouter_model_2, self.config.openrouter_model_3, self.config.openrouter_model_4, self.config.openrouter_model_5])
        self.active_model_combo.setCurrentText(self.config.openrouter_model)
        active_model_layout.addWidget(self.active_model_combo)
        basic_layout.addLayout(active_model_layout)
        
        for le in self.model_inputs:
            le.textChanged.connect(self._sync_active_model_combo)
            
        basic_layout.addStretch()
        self.stack.addWidget(page_basic)
        
        # -----------------------------------------------------
        # 3. Local Page
        # -----------------------------------------------------
        page_local = QWidget()
        local_layout = QVBoxLayout(page_local)
        local_layout.setContentsMargins(0, 0, 0, 0)
        
        local_layout.addWidget(QLabel("Ollama Chat Model (e.g. llama3):"))
        self.ollama_chat_combo = QComboBox()
        self.ollama_chat_combo.setEditable(True)
        local_layout.addWidget(self.ollama_chat_combo)
        
        local_layout.addWidget(QLabel("Ollama Coding Model (e.g. deepseek-coder):"))
        self.ollama_coding_combo = QComboBox()
        self.ollama_coding_combo.setEditable(True)
        self.ollama_coding_combo.addItem("(none - use Chat model)")
        local_layout.addWidget(self.ollama_coding_combo)
        local_layout.addWidget(QLabel("<small><i>Coding model is used for code questions and screen analysis. Leave as '(none)' to use Chat model.</i></small>"))
        
        local_layout.addWidget(QLabel("Ollama Vision Model (e.g. llava, minicpm-v):"))
        self.ollama_vision_combo = QComboBox()
        self.ollama_vision_combo.setEditable(True)
        self.ollama_vision_combo.addItem("(none - use Chat model)")
        local_layout.addWidget(self.ollama_vision_combo)
        local_layout.addWidget(QLabel("<small><i>Vision model is used for screen captures and screenshots. Leave as '(none)' to use Chat model.</i></small>"))
        
        self.btn_validate_local = QPushButton("Fetch & Validate Local Models")
        self.btn_validate_local.clicked.connect(self._validate_local)
        local_layout.addWidget(self.btn_validate_local)
        
        # Initial load
        self._validate_local(silent=True)
            
        self.ollama_chat_combo.setCurrentText(self.config.ollama_model)
        coding_model_saved = getattr(self.config, 'ollama_coding_model', '')
        if coding_model_saved: self.ollama_coding_combo.setCurrentText(coding_model_saved)
        else: self.ollama_coding_combo.setCurrentText("(none - use Chat model)")
            
        vision_model_saved = getattr(self.config, 'ollama_vision_model', '')
        if vision_model_saved: self.ollama_vision_combo.setCurrentText(vision_model_saved)
        else: self.ollama_vision_combo.setCurrentText("(none - use Chat model)")
            
        local_layout.addStretch()
        self.stack.addWidget(page_local)
        
        # -----------------------------------------------------
        # Setup Logic
        # -----------------------------------------------------
        current_mode = getattr(self.config, 'activation_mode', 'basic')
        if current_mode == 'premium': self.mode_dropdown.setCurrentIndex(0)
        elif current_mode == 'local': self.mode_dropdown.setCurrentIndex(2)
        else: self.mode_dropdown.setCurrentIndex(1)
            
        self.stack.setCurrentIndex(self.mode_dropdown.currentIndex())
        self.mode_dropdown.currentIndexChanged.connect(self.stack.setCurrentIndex)
        
        layout.addStretch()
        scroll.setWidget(inner)
        main_layout.addWidget(scroll)
        self.pages.addWidget(page)

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
            r = httpx.get("https://openrouter.ai/api/v1/auth/key", headers={"Authorization": f"Bearer {key}"}, timeout=5.0)
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
            self.ollama_vision_combo.clear()
            
            self.ollama_chat_combo.addItems(available_models)
            self.ollama_coding_combo.addItem("(none - use Chat model)")
            self.ollama_coding_combo.addItems(available_models)
            self.ollama_vision_combo.addItem("(none - use Chat model)")
            self.ollama_vision_combo.addItems(available_models)
            
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
            lbl.setText("ÃƒÂ¢Ã‚ÂÃ‚Â³")
            
        key = self.key_input.text().strip()
        models = [le.text().strip() for le in self.model_inputs if le.text().strip()]
        
        self.validator = ValidatorThread(key, models, self.config.openrouter_base_url)
        self.validator.result_ready.connect(self.on_validation_result)
        self.validator.finished_validation.connect(self.on_validation_finished)
        self.validator.start()
        
    def on_validation_result(self, model_name, is_valid, err):
        for idx, le in enumerate(self.model_inputs):
            if le.text().strip() == model_name:
                self.model_status_labels[idx].setText("ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦" if is_valid else "ÃƒÂ¢Ã‚ÂÃ…â€™")
                self.model_status_labels[idx].setToolTip(err if not is_valid else "Working")
                
    def on_validation_finished(self):
        self.btn_validate.setEnabled(True)
        self.btn_validate.setText("Validate Key & Models")
        # Clear loading for empty fields
        for le, lbl in zip(self.model_inputs, self.model_status_labels):
            if not le.text().strip() and lbl.text() == "ÃƒÂ¢Ã‚ÂÃ‚Â³":
                lbl.setText("")
                
    def setup_window_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Colors
        self.q_color = self.config.ui_question_color
        self.a_color = self.config.ui_answer_color
        color_layout = QVBoxLayout()
        
        q_color_row = QHBoxLayout()
        q_color_row.addWidget(QLabel("Question Color:"))
        self.btn_q_color = QPushButton()
        self.btn_q_color.setFixedSize(30, 30)
        self.btn_q_color.setCursor(Qt.PointingHandCursor)
        self.btn_q_color.setStyleSheet(f"background-color: {self.q_color}; border: 1px solid #777; border-radius: 4px;")
        self.btn_q_color.clicked.connect(self.pick_q_color)
        q_color_row.addWidget(self.btn_q_color)
        q_color_row.addStretch()
        
        a_color_row = QHBoxLayout()
        a_color_row.addWidget(QLabel("Answer Color:"))
        self.btn_a_color = QPushButton()
        self.btn_a_color.setFixedSize(30, 30)
        self.btn_a_color.setCursor(Qt.PointingHandCursor)
        self.btn_a_color.setStyleSheet(f"background-color: {self.a_color}; border: 1px solid #777; border-radius: 4px;")
        self.btn_a_color.clicked.connect(self.pick_a_color)
        a_color_row.addWidget(self.btn_a_color)
        a_color_row.addStretch()
        
        color_layout.addLayout(q_color_row)
        color_layout.addLayout(a_color_row)
        layout.addLayout(color_layout)
        
        # Theme
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["system", "dark", "light"])
        self.theme_combo.setCurrentText(self.config.ui_theme_mode)
        self.theme_combo.setMaximumWidth(120)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()
        layout.addLayout(theme_layout)
        
        # Sliders
        # Opacity
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("Window Opacity (%):"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(self.config.ui_opacity)
        self.opacity_val_label = QLabel(str(self.opacity_slider.value()))
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_val_label.setText(str(v)))
        self.opacity_slider.setMaximumWidth(120)
        opacity_layout.addWidget(self.opacity_slider)
        opacity_layout.addWidget(self.opacity_val_label)
        opacity_layout.addStretch()
        layout.addLayout(opacity_layout)
        
        # Font Size
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Font Size (px):"))
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(10, 32)
        self.font_slider.setValue(self.config.ui_font_size)
        self.font_val_label = QLabel(str(self.font_slider.value()))
        self.font_slider.valueChanged.connect(lambda v: self.font_val_label.setText(str(v)))
        self.font_slider.setMaximumWidth(120)
        font_layout.addWidget(self.font_slider)
        font_layout.addWidget(self.font_val_label)
        font_layout.addStretch()
        layout.addLayout(font_layout)
        
        # Memory
        hist_layout = QHBoxLayout()
        hist_layout.addWidget(QLabel("Memory (past Q&A):"))
        self.hist_slider = QSlider(Qt.Horizontal)
        self.hist_slider.setRange(1, 20)
        self.hist_slider.setValue(max(1, self.config.conversation_history_depth))
        self.hist_val_label = QLabel(str(self.hist_slider.value()))
        self.hist_slider.valueChanged.connect(lambda v: self.hist_val_label.setText(str(v)))
        self.hist_slider.setMaximumWidth(120)
        hist_layout.addWidget(self.hist_slider)
        hist_layout.addWidget(self.hist_val_label)
        hist_layout.addStretch()
        layout.addLayout(hist_layout)
        
        
        # Checkboxes (Toggles)
        self.chk_taskbar = QCheckBox("Show in Taskbar")
        self.chk_taskbar.setChecked(self.config.ui_show_in_taskbar)
        layout.addWidget(self.chk_taskbar)
        
        self.chk_tray = QCheckBox("Show in System Tray")
        self.chk_tray.setChecked(self.config.ui_show_tray)
        layout.addWidget(self.chk_tray)
        
        self.chk_pin = QCheckBox("Always on Top (Pinned)")
        self.chk_pin.setChecked(self.config.ui_always_on_top)
        layout.addWidget(self.chk_pin)
        
        self.chk_pos = QCheckBox("Remember Window Position")
        self.chk_pos.setChecked(self.config.ui_remember_position)
        layout.addWidget(self.chk_pos)
        

        
        layout.addStretch()
        self.pages.addWidget(page)
        
    def setup_audio_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        
        # 1. User Audio Capture
        inner_layout.addWidget(QLabel("--- 1. User Audio Capture (Microphone) ---"))
        
        user_device_layout = QHBoxLayout()
        user_device_layout.addWidget(QLabel("Input Device:"))
        self.user_device_combo = QComboBox()
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
        self.user_device_combo.setMaximumWidth(250)
        user_device_layout.addWidget(self.user_device_combo)
        user_device_layout.addStretch()
        inner_layout.addLayout(user_device_layout)
        
        self.chk_mute_mic = QCheckBox("Mute User Mic")
        self.chk_mute_mic.setChecked(getattr(self.config, 'mute_user_mic', False))
        inner_layout.addWidget(self.chk_mute_mic)
        
        inner_layout.addSpacing(10)
        
        # 2. Interviewer Audio Capture
        inner_layout.addWidget(QLabel("--- 2. Interviewer Audio Capture (System Audio) ---"))
        
        sys_device_layout = QHBoxLayout()
        sys_device_layout.addWidget(QLabel("Speaker Device (Loopback):"))
        self.sys_device_combo = QComboBox()
        self.sys_device_combo.addItem("Default Windows Output")
        try:
            import soundcard as sc
            for s in sc.all_speakers():
                self.sys_device_combo.addItem(s.name)
        except Exception:
            pass
        saved_sys_spk = getattr(self.config, 'system_audio_device', 'Default Windows Output')
        self.sys_device_combo.setCurrentText(saved_sys_spk)
        self.sys_device_combo.setMaximumWidth(250)
        sys_device_layout.addWidget(self.sys_device_combo)
        sys_device_layout.addStretch()
        inner_layout.addLayout(sys_device_layout)
        
        self.chk_mute_sys = QCheckBox("Mute System Audio Capture")
        self.chk_mute_sys.setChecked(getattr(self.config, 'mute_system_audio', False))
        inner_layout.addWidget(self.chk_mute_sys)
        
        inner_layout.addSpacing(10)
        
        # 3. Voice Output
        inner_layout.addWidget(QLabel("--- 3. Voice Output (Voro TTS) ---"))
        tts_speed_layout = QHBoxLayout()
        tts_speed_layout.addWidget(QLabel("Voice Speed:"))
        self.tts_speed_combo = QComboBox()
        self.tts_speed_combo.addItems(["-50%", "-25%", "+0%", "+25%", "+50%", "+75%", "+100%"])
        self.tts_speed_combo.setCurrentText(getattr(self.config, 'ui_tts_rate', '+0%'))
        self.tts_speed_combo.setMaximumWidth(120)
        tts_speed_layout.addWidget(self.tts_speed_combo)
        tts_speed_layout.addStretch()
        inner_layout.addLayout(tts_speed_layout)
        
        tts_vol_layout = QHBoxLayout()
        tts_vol_layout.addWidget(QLabel("Voice Volume (0-100):"))
        from PySide6.QtWidgets import QSlider
        from PySide6.QtCore import Qt
        self.tts_vol_slider = QSlider(Qt.Horizontal)
        self.tts_vol_slider.setRange(0, 100)
        self.tts_vol_slider.setValue(getattr(self.config, 'ui_tts_volume', 100))
        self.tts_vol_label = QLabel(str(self.tts_vol_slider.value()))
        self.tts_vol_slider.valueChanged.connect(lambda v: self.tts_vol_label.setText(str(v)))
        self.tts_vol_slider.setMaximumWidth(120)
        tts_vol_layout.addWidget(self.tts_vol_slider)
        tts_vol_layout.addWidget(self.tts_vol_label)
        tts_vol_layout.addStretch()
        inner_layout.addLayout(tts_vol_layout)
        
        self.chk_tts_muted = QCheckBox("Mute Voro Voice (TTS)")
        self.chk_tts_muted.setChecked(getattr(self.config, 'ui_tts_muted', False))
        inner_layout.addWidget(self.chk_tts_muted)
        
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self.pages.addWidget(page)

    def setup_shortcuts_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        
        # 1. Activation Mode
        inner_layout.addWidget(QLabel("--- 1. Activation Mode Shortcut ---"))
        
        cycle_mode_layout = QHBoxLayout()
        cycle_mode_layout.addWidget(QLabel("Cycle Activation Mode Hotkey:"))
        self.cycle_mode_hotkey_input = QLineEdit(getattr(self.config, 'ui_cycle_mode_hotkey', 'ctrl+shift+v'))
        cycle_mode_layout.addWidget(self.cycle_mode_hotkey_input)
        inner_layout.addLayout(cycle_mode_layout)
        
        inner_layout.addSpacing(10)
        
        # 2. Window Shortcuts
        inner_layout.addWidget(QLabel("--- 2. Window Shortcuts ---"))
        
        summon_layout = QHBoxLayout()
        summon_layout.addWidget(QLabel("Global Summon Hotkey:"))
        self.hotkey_input = QLineEdit(self.config.ui_global_hotkey)
        summon_layout.addWidget(self.hotkey_input)
        inner_layout.addLayout(summon_layout)
        
        taskbar_hotkey_layout = QHBoxLayout()
        taskbar_hotkey_layout.addWidget(QLabel("Toggle Taskbar Hotkey:"))
        self.taskbar_hotkey_input = QLineEdit(getattr(self.config, 'ui_taskbar_hotkey', 'ctrl+shift+t'))
        taskbar_hotkey_layout.addWidget(self.taskbar_hotkey_input)
        inner_layout.addLayout(taskbar_hotkey_layout)
        
        maximize_layout = QHBoxLayout()
        maximize_layout.addWidget(QLabel("Maximize Window Hotkey:"))
        self.maximize_hotkey_input = QLineEdit(getattr(self.config, 'ui_maximize_hotkey', 'F11'))
        maximize_layout.addWidget(self.maximize_hotkey_input)
        inner_layout.addLayout(maximize_layout)
        
        inner_layout.addSpacing(10)
        
        # 3. Audio Shortcuts
        inner_layout.addWidget(QLabel("--- 3. Audio Shortcuts ---"))
        
        mute_mic_layout = QHBoxLayout()
        mute_mic_layout.addWidget(QLabel("Mute User Mic Hotkey:"))
        self.mute_mic_hotkey_input = QLineEdit(getattr(self.config, 'ui_mute_mic_hotkey', 'ctrl+shift+m'))
        mute_mic_layout.addWidget(self.mute_mic_hotkey_input)
        inner_layout.addLayout(mute_mic_layout)
        
        mute_sys_layout = QHBoxLayout()
        mute_sys_layout.addWidget(QLabel("Mute System Audio Hotkey:"))
        self.mute_sys_hotkey_input = QLineEdit(getattr(self.config, 'ui_mute_sys_hotkey', 'ctrl+shift+a'))
        mute_sys_layout.addWidget(self.mute_sys_hotkey_input)
        inner_layout.addLayout(mute_sys_layout)
        
        tts_mute_layout = QHBoxLayout()
        tts_mute_layout.addWidget(QLabel("Mute Voice (TTS) Hotkey:"))
        self.tts_mute_hotkey_input = QLineEdit(getattr(self.config, 'ui_tts_mute_hotkey', 'ctrl+shift+x'))
        tts_mute_layout.addWidget(self.tts_mute_hotkey_input)
        inner_layout.addLayout(tts_mute_layout)
        
        inner_layout.addSpacing(10)
        
        # 4. Others
        inner_layout.addWidget(QLabel("--- 4. Others ---"))
        
        hint_layout = QHBoxLayout()
        hint_layout.addWidget(QLabel("Hint Mode Hotkey:"))
        self.hint_hotkey_input = QLineEdit(getattr(self.config, 'ui_hint_hotkey', 'ctrl+shift+h'))
        hint_layout.addWidget(self.hint_hotkey_input)
        inner_layout.addLayout(hint_layout)
        
        snip_layout = QHBoxLayout()
        snip_layout.addWidget(QLabel("Snip Mode Hotkey:"))
        self.snip_hotkey_input = QLineEdit(getattr(self.config, 'ui_snip_hotkey', 'ctrl+shift+s'))
        snip_layout.addWidget(self.snip_hotkey_input)
        inner_layout.addLayout(snip_layout)
        
        inner_layout.addWidget(QLabel("<small><i>Hotkeys take effect instantly upon saving.</i></small>"))
        
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self.pages.addWidget(page)

    def setup_profile_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        
        # Profile Selector
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
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
        
        inner_layout.addWidget(QLabel("--- Personal Knowledge ---"))
        
        self.profile_name = QLineEdit()
        inner_layout.addWidget(QLabel("Name:"))
        inner_layout.addWidget(self.profile_name)
        
        self.profile_education = QLineEdit()
        inner_layout.addWidget(QLabel("Education:"))
        inner_layout.addWidget(self.profile_education)
        
        self.profile_skills = QLineEdit()
        inner_layout.addWidget(QLabel("Skills (comma separated):"))
        inner_layout.addWidget(self.profile_skills)
        
        self.profile_projects = QTextEdit()
        self.profile_projects.setMaximumHeight(80)
        inner_layout.addWidget(QLabel("Projects / Experience:"))
        inner_layout.addWidget(self.profile_projects)
        
        # PDF Resume Upload
        inner_layout.addWidget(QLabel("Resume (PDF):"))
        self.lbl_resume_status = QLabel("Resume: Not Uploaded")
        self.lbl_resume_status.setStyleSheet("color: #AAAAAA;")
        inner_layout.addWidget(self.lbl_resume_status)
        
        btn_upload = QPushButton("Upload PDF Resume")
        btn_upload.clicked.connect(self.upload_pdf_resume)
        inner_layout.addWidget(btn_upload)
        
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
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        
        inner_layout.addWidget(QLabel("--- Company & Interview Details ---"))
        inner_layout.addWidget(QLabel("Note: These details are attached to your currently selected Profile."))
        
        self.comp_name = QLineEdit()
        inner_layout.addWidget(QLabel("Company Name:"))
        inner_layout.addWidget(self.comp_name)
        
        self.comp_role = QLineEdit()
        inner_layout.addWidget(QLabel("Role Applying For:"))
        inner_layout.addWidget(self.comp_role)
        
        self.comp_details = QTextEdit()
        self.comp_details.setMaximumHeight(80)
        inner_layout.addWidget(QLabel("Company Details:"))
        inner_layout.addWidget(self.comp_details)
        
        self.comp_info = QTextEdit()
        self.comp_info.setMaximumHeight(80)
        inner_layout.addWidget(QLabel("Important Info:"))
        inner_layout.addWidget(self.comp_info)
        
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
            self.lbl_resume_status.setText(f"Resume: Loaded ({len(self._extracted_resume_text)} characters)")
            self.lbl_resume_status.setStyleSheet("color: #00FF00;")
        else:
            self.lbl_resume_status.setText("Resume: Not Uploaded")
            self.lbl_resume_status.setStyleSheet("color: #AAAAAA;")
            
        self.comp_name.setText(ctx.interview.company)
        self.comp_role.setText(ctx.interview.role)
        self.comp_details.setPlainText(ctx.interview.company_details)
        self.comp_info.setPlainText(ctx.interview.important_info)
        
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
                self.lbl_resume_status.setText(f"Resume: Loaded ({len(self._extracted_resume_text)} characters)")
                self.lbl_resume_status.setStyleSheet("color: #00FF00;")
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
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        
        inner_layout.addWidget(QLabel("--- Features ---"))
        self.chk_web_search = QCheckBox("Enable Live Web Search (DuckDuckGo)")
        self.chk_web_search.setChecked(self.config.enable_web_search)
        inner_layout.addWidget(self.chk_web_search)
        
        self.chk_auto_monitor = QCheckBox("Enable Auto-Monitor (Silent Screen Tracking)")
        self.chk_auto_monitor.setChecked(getattr(self.config, 'enable_auto_monitor', False))
        inner_layout.addWidget(self.chk_auto_monitor)
        
        inner_layout.addSpacing(10)
        inner_layout.addWidget(QLabel("--- Optical Character Recognition (OCR) ---"))
        
        ocr_device_layout = QHBoxLayout()
        ocr_device_layout.addWidget(QLabel("Compute Device:"))
        self.ocr_device_combo = QComboBox()
        self.ocr_device_combo.addItems(["cuda", "cpu"])
        self.ocr_device_combo.setCurrentText(getattr(self.config, 'ocr_compute_device', 'cuda'))
        self.ocr_device_combo.setMaximumWidth(120)
        ocr_device_layout.addWidget(self.ocr_device_combo)
        ocr_device_layout.addStretch()
        inner_layout.addLayout(ocr_device_layout)
        
        tess_layout = QHBoxLayout()
        tess_layout.addWidget(QLabel("Tesseract Path (If used):"))
        tess_val = getattr(self.config, 'tesseract_cmd_path', '')
        if not tess_val: tess_val = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        self.tess_path_input = QLineEdit(tess_val)
        tess_layout.addWidget(self.tess_path_input)
        self.btn_tess_browse = QPushButton("Browse")
        self.btn_tess_browse.clicked.connect(self.browse_tesseract_path)
        tess_layout.addWidget(self.btn_tess_browse)
        inner_layout.addLayout(tess_layout)
        
        inner_layout.addSpacing(10)
        inner_layout.addWidget(QLabel("--- AI Engine Personality & Tone ---"))
        
        ai_tone_layout = QHBoxLayout()
        ai_tone_layout.addWidget(QLabel("AI Tone:"))
        self.ai_tone_combo = QComboBox()
        self.ai_tone_combo.addItems(["Conversational (Script)", "Conversational (Hinglish)", "Direct & Technical", "Supportive & Encouraging"])
        self.ai_tone_combo.setCurrentText(getattr(self.config, 'ai_tone', 'Conversational (Script)'))
        self.ai_tone_combo.setMaximumWidth(250)
        ai_tone_layout.addWidget(self.ai_tone_combo)
        ai_tone_layout.addStretch()
        inner_layout.addLayout(ai_tone_layout)
        
        inner_layout.addSpacing(10)
        inner_layout.addWidget(QLabel("--- Speech-to-Text (STT) Options ---"))
        
        stt_device_layout = QHBoxLayout()
        stt_device_layout.addWidget(QLabel("Compute Device:"))
        self.stt_device_combo = QComboBox()
        self.stt_device_combo.addItems(["cuda", "cpu"])
        self.stt_device_combo.setCurrentText(getattr(self.config, 'stt_device', 'cpu'))
        self.stt_device_combo.setMaximumWidth(120)
        stt_device_layout.addWidget(self.stt_device_combo)
        stt_device_layout.addStretch()
        inner_layout.addLayout(stt_device_layout)
        
        stt_model_layout = QHBoxLayout()
        stt_model_layout.addWidget(QLabel("STT Model Size:"))
        self.stt_model_combo = QComboBox()
        self.stt_model_combo.addItems(["tiny.en", "tiny", "base.en", "base", "small.en", "small", "medium.en", "medium", "large"])
        self.stt_model_combo.setCurrentText(getattr(self.config, 'stt_model_size', 'base.en'))
        self.stt_model_combo.setMaximumWidth(120)
        stt_model_layout.addWidget(self.stt_model_combo)
        stt_model_layout.addStretch()
        inner_layout.addLayout(stt_model_layout)
        
        inner_layout.addWidget(QLabel("STT Context Prompt (Helps with heavy accents/jargon):"))
        from PySide6.QtWidgets import QTextEdit
        self.stt_context_input = QTextEdit()
        self.stt_context_input.setMaximumHeight(80)
        self.stt_context_input.setPlainText(getattr(self.config, 'stt_context_prompt', ''))
        inner_layout.addWidget(self.stt_context_input)
        

        
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

    def _validate_local(self, silent=False):
        pass

    def validate_models(self):
        QMessageBox.information(self, "Validation", "Model validation skipped.")

    def on_validation_result(self, model_name, is_valid, err):
        pass

    def on_validation_finished(self):
        pass

    def save_settings(self):
        self.save_current_profile_fields()
        idx = self.mode_dropdown.currentIndex()
        if idx == 0:
            mode = "premium"
            if not self.premium_key_input.text().strip() or not self.premium_model_input.text().strip():
                QMessageBox.warning(self, "Validation Error", "Premium API Key and Model Name cannot be empty.")
                return
        elif idx == 2:
            mode = "local"
        else:
            mode = "basic"
            if not self.key_input.text().strip() or not self.active_model_combo.currentText().strip():
                QMessageBox.warning(self, "Validation Error", "Basic Activation Key and Active Model cannot be empty.")
                return

        if not os.path.exists(self.env_path):
            with open(self.env_path, "w") as f: pass

        set_key(self.env_path, "ACTIVATION_MODE", mode)
        
        # Premium
        set_key(self.env_path, "PREMIUM_API_KEY", self.premium_key_input.text().strip())
        set_key(self.env_path, "PREMIUM_MODEL", self.premium_model_input.text().strip())
        
        # Basic
        set_key(self.env_path, "OPENROUTER_API_KEY", self.key_input.text().strip())
        set_key(self.env_path, "OPENROUTER_MODEL", self.active_model_combo.currentText().strip())
        
        for i, le in enumerate(self.model_inputs):
            key = "OPENROUTER_MODEL" if i == 0 else f"OPENROUTER_MODEL_{i+1}"
            set_key(self.env_path, key, le.text().strip())

        # Local
        set_key(self.env_path, "OLLAMA_MODEL", self.ollama_chat_combo.currentText().strip())
        coding_text = self.ollama_coding_combo.currentText().strip()
        set_key(self.env_path, "OLLAMA_CODING_MODEL", "" if "(none" in coding_text else coding_text)
        vision_text = self.ollama_vision_combo.currentText().strip()
        set_key(self.env_path, "OLLAMA_VISION_MODEL", "" if "(none" in vision_text else vision_text)

        # Window
        set_key(self.env_path, "UI_OPACITY", str(self.opacity_slider.value()))
        set_key(self.env_path, "UI_THEME_MODE", self.theme_combo.currentText())
        set_key(self.env_path, "UI_FONT_SIZE", str(self.font_slider.value()))
        set_key(self.env_path, "CONVERSATION_HISTORY_DEPTH", str(self.hist_slider.value()))
        set_key(self.env_path, "UI_SHOW_IN_TASKBAR", str(self.chk_taskbar.isChecked()))
        set_key(self.env_path, "UI_SHOW_TRAY", str(self.chk_tray.isChecked()))
        set_key(self.env_path, "UI_ALWAYS_ON_TOP", str(self.chk_pin.isChecked()))
        set_key(self.env_path, "UI_REMEMBER_POSITION", str(self.chk_pos.isChecked()))
        set_key(self.env_path, "MUTE_USER_MIC", str(self.chk_mute_mic.isChecked()))
        set_key(self.env_path, "MUTE_SYSTEM_AUDIO", str(self.chk_mute_sys.isChecked()))
        if hasattr(self, 'q_color'):
            set_key(self.env_path, "UI_QUESTION_COLOR", self.q_color)
        if hasattr(self, 'a_color'):
            set_key(self.env_path, "UI_ANSWER_COLOR", self.a_color)

        # Shortcuts
        if hasattr(self, 'hotkey_input'): set_key(self.env_path, "UI_GLOBAL_HOTKEY", self.hotkey_input.text().strip())
        if hasattr(self, 'hint_hotkey_input'): set_key(self.env_path, "UI_HINT_HOTKEY", self.hint_hotkey_input.text().strip())
        if hasattr(self, 'snip_hotkey_input'): set_key(self.env_path, "UI_SNIP_HOTKEY", self.snip_hotkey_input.text().strip())
        if hasattr(self, 'maximize_hotkey_input'): set_key(self.env_path, "UI_MAXIMIZE_HOTKEY", self.maximize_hotkey_input.text().strip())
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
        if hasattr(self, 'stt_context_input'):
            set_key(self.env_path, "STT_CONTEXT_PROMPT", self.stt_context_input.toPlainText().strip())
        if hasattr(self, 'tts_speed_combo'):
            set_key(self.env_path, "UI_TTS_RATE", self.tts_speed_combo.currentText())
        if hasattr(self, 'chk_tts_muted'):
            set_key(self.env_path, "UI_TTS_MUTED", str(self.chk_tts_muted.isChecked()))

        import subprocess
        import sys
        from PySide6.QtWidgets import QApplication
        
        self.accept()
        subprocess.Popen([sys.executable] + sys.argv)
        QApplication.quit()

    def pick_q_color(self):
        color = QColorDialog.getColor(QColor(getattr(self, 'q_color', '#FFFFFF')), self, "Select Question Color")
        if color.isValid():
            self.q_color = color.name()
            self.btn_q_color.setStyleSheet(f"background-color: {self.q_color}; border: 1px solid #777; border-radius: 4px;")

    def pick_a_color(self):
        color = QColorDialog.getColor(QColor(getattr(self, 'a_color', '#90EE90')), self, "Select Answer Color")
        if color.isValid():
            self.a_color = color.name()
            self.btn_a_color.setStyleSheet(f"background-color: {self.a_color}; border: 1px solid #777; border-radius: 4px;")

    def _apply_privacy_flag(self):
        import ctypes
        try:
            if getattr(self.config, 'ui_stealth_mode', True):
                hwnd = self.winId()
                ctypes.windll.user32.SetWindowDisplayAffinity(int(hwnd), 0x00000011)
        except Exception:
            pass
