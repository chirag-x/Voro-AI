
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
