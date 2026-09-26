import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QStackedWidget, QWidget)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

class TutorialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Voro")
        self.setFixedSize(500, 350)
        self.setStyleSheet("""
            QDialog {
                background-color: #222;
                color: #EEE;
            }
            QLabel {
                font-size: 14px;
            }
            QPushButton {
                background-color: #0055A4;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0066CC;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        
        # Slide 1: Welcome & Hotkeys
        s1 = QWidget()
        l1 = QVBoxLayout(s1)
        l1.addWidget(QLabel("<h2>Welcome to Voro 🎙️</h2>"))
        l1.addWidget(QLabel("Voro is your AI copilot. Here are your main hotkeys:"))
        l1.addWidget(QLabel("<b>Ctrl+Space</b> : Hold to talk (Global)"))
        l1.addWidget(QLabel("<b>Ctrl+Shift+H</b> : Hint Mode (Listens, doesn't speak)"))
        l1.addWidget(QLabel("<b>Ctrl+Shift+S</b> : Screen Snip (Take a screenshot)"))
        l1.addWidget(QLabel("<b>Ctrl+Shift+T</b> : Show/Hide the Voro Window"))
        l1.addStretch()
        self.stack.addWidget(s1)
        
        # Slide 2: Microphone & Audio
        s2 = QWidget()
        l2 = QVBoxLayout(s2)
        l2.addWidget(QLabel("<h2>Microphone Setup 🎧</h2>"))
        l2.addWidget(QLabel("Voro needs to hear you clearly."))
        l2.addWidget(QLabel("1. Open the <b>Settings</b> menu (gear icon)."))
        l2.addWidget(QLabel("2. Go to the <b>Audio</b> tab."))
        l2.addWidget(QLabel("3. Select your exact microphone from the dropdown."))
        l2.addWidget(QLabel("You can also select your PC Speaker to let Voro hear meetings!"))
        l2.addStretch()
        self.stack.addWidget(s2)
        
        # Slide 3: AI Models
        s3 = QWidget()
        l3 = QVBoxLayout(s3)
        l3.addWidget(QLabel("<h2>AI Models 🧠</h2>"))
        l3.addWidget(QLabel("Voro uses Ollama to run completely offline."))
        l3.addWidget(QLabel("Make sure you have Ollama installed and running."))
        l3.addWidget(QLabel("We recommend downloading <b>qwen2.5:7b</b> for general chat."))
        l3.addWidget(QLabel("You're all set! Click Finish to start using Voro."))
        l3.addStretch()
        self.stack.addWidget(s3)
        
        btn_layout = QHBoxLayout()
        self.btn_prev = QPushButton("Previous")
        self.btn_prev.clicked.connect(self.prev_slide)
        self.btn_prev.hide()
        
        self.btn_next = QPushButton("Next")
        self.btn_next.clicked.connect(self.next_slide)
        
        btn_layout.addWidget(self.btn_prev)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_next)
        layout.addLayout(btn_layout)
        
    def prev_slide(self):
        cur = self.stack.currentIndex()
        if cur > 0:
            self.stack.setCurrentIndex(cur - 1)
        self._update_btns()
            
    def next_slide(self):
        cur = self.stack.currentIndex()
        if cur < self.stack.count() - 1:
            self.stack.setCurrentIndex(cur + 1)
            self._update_btns()
        else:
            self.accept()
            
    def _update_btns(self):
        cur = self.stack.currentIndex()
        self.btn_prev.setVisible(cur > 0)
        if cur == self.stack.count() - 1:
            self.btn_next.setText("Finish")
        else:
            self.btn_next.setText("Next")

