import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTextEdit, QPushButton, QMessageBox, QFileDialog, QScrollArea, QWidget
)
from PySide6.QtCore import Qt

from app.context.manager import ContextManager
from app.ui.theme import get_theme_colors

class UserProfileDialog(QDialog):
    def __init__(self, context_manager: ContextManager, parent=None):
        super().__init__(parent)
        self.context_manager = context_manager
        
        from app.core.config import load_config
        config = load_config()
        self.theme = get_theme_colors(config.ui_theme_mode)
        
        self.setWindowTitle("User Profile & Details")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)
        
        # Make the dialog stay on top like settings
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        layout = QVBoxLayout(self)
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Name
        content_layout.addWidget(QLabel("Name:"))
        self.name_input = QLineEdit(self.context_manager.current_context.personal.name)
        content_layout.addWidget(self.name_input)
        
        # Education
        content_layout.addWidget(QLabel("Education:"))
        self.edu_input = QLineEdit(self.context_manager.current_context.personal.education)
        content_layout.addWidget(self.edu_input)
        
        # Skills
        content_layout.addWidget(QLabel("Skills (comma-separated):"))
        self.skills_input = QLineEdit(", ".join(self.context_manager.current_context.personal.skills))
        content_layout.addWidget(self.skills_input)
        
        # Projects
        content_layout.addWidget(QLabel("Projects / Experience:"))
        self.projects_input = QTextEdit()
        self.projects_input.setPlainText(self.context_manager.current_context.personal.projects)
        self.projects_input.setMaximumHeight(80)
        content_layout.addWidget(self.projects_input)
        
        # Resume
        resume_header_layout = QHBoxLayout()
        resume_header_layout.addWidget(QLabel("Resume / Bio (Text):"))
        upload_btn = QPushButton("Upload .txt Resume")
        upload_btn.clicked.connect(self.upload_resume)
        resume_header_layout.addWidget(upload_btn)
        
        content_layout.addLayout(resume_header_layout)
        
        self.resume_input = QTextEdit()
        self.resume_input.setPlainText(self.context_manager.current_context.personal.resume_text)
        content_layout.addWidget(self.resume_input)
        
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Profile")
        save_btn.clicked.connect(self.save_profile)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        # Styling
        self.setStyleSheet(
            f"background-color: {self.theme['bg']};"
            f"color: {self.theme['base_text']};"
            "QLineEdit, QTextEdit { border: 1px solid gray; padding: 4px; }"
        )
        self._apply_privacy_flag()

    def _apply_privacy_flag(self):
        import sys
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = int(self.winId())
                WDA_EXCLUDEFROMCAPTURE = 0x11
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
            except Exception:
                pass

    def upload_resume(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Resume Text File", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.resume_input.setPlainText(content)
                    QMessageBox.information(self, "Success", "Resume text loaded successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not read file:\n{e}")

    def save_profile(self):
        name = self.name_input.text().strip()
        education = self.edu_input.text().strip()
        skills_raw = self.skills_input.text().strip()
        skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
        projects = self.projects_input.toPlainText().strip()
        resume_text = self.resume_input.toPlainText().strip()
        
        self.context_manager.update_personal(
            name=name,
            education=education,
            skills=skills,
            projects=projects,
            resume_text=resume_text
        )
        
        QMessageBox.information(self, "Success", "User profile saved! Voro will use this context in its answers.")
        self.accept()
