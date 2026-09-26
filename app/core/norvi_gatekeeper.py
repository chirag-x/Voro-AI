import os
import sys
import json
import time
import uuid
import platform
import urllib.request
import urllib.error
from app.utils.logging import logger
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QApplication
from PySide6.QtCore import Qt

API_BASE_URL = os.getenv("NORVI_API_URL", "http://localhost:4321")
LEASE_FILE = os.path.join(os.path.expanduser("~"), ".norvi_voro_lease")

def get_hardware_id():
    mac = uuid.getnode()
    return f"{platform.node()}-{mac}"

def load_lease():
    if not os.path.exists(LEASE_FILE):
        return None
    try:
        with open(LEASE_FILE, 'r') as f:
            data = json.load(f)
            # Check expiry
            if data.get("expires_at"):
                exp = data["expires_at"]
                if time.time() > exp:
                    return None
            return data
    except Exception:
        return None

def save_lease(token, expires_at):
    try:
        with open(LEASE_FILE, 'w') as f:
            json.dump({"token": token, "expires_at": expires_at}, f)
    except Exception as e:
        logger.error(f"Failed to save lease: {e}")

class ActivationDialog(QDialog):
    def __init__(self, product_slug, parent=None):
        super().__init__(parent)
        self.product_slug = product_slug
        self.setWindowTitle("NORVI Activation")
        self.setFixedSize(400, 350)
        self.setStyleSheet("background-color: #121212; color: #ffffff;")
        
        layout = QVBoxLayout(self)
        
        title = QLabel("Agent Activation")
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        desc = QLabel(f"Please log in to your NORVI account and enter your activation key for {product_slug.capitalize()}.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaaaaa; margin-bottom: 20px;")
        layout.addWidget(desc)
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("NORVI Email")
        self.email_input.setStyleSheet("padding: 10px; border: 1px solid #333; border-radius: 5px; background: #1e1e1e;")
        layout.addWidget(self.email_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet("padding: 10px; border: 1px solid #333; border-radius: 5px; background: #1e1e1e;")
        layout.addWidget(self.password_input)
        
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Activation Key (e.g., NORVI-XXXX-...)")
        self.key_input.setStyleSheet("padding: 10px; border: 1px solid #333; border-radius: 5px; background: #1e1e1e; margin-bottom: 20px;")
        layout.addWidget(self.key_input)
        
        self.activate_btn = QPushButton("Activate & Launch")
        self.activate_btn.setStyleSheet("padding: 12px; background-color: #4CAF50; color: white; border: none; border-radius: 5px; font-weight: bold;")
        self.activate_btn.clicked.connect(self.do_activate)
        layout.addWidget(self.activate_btn)
        
    def do_activate(self):
        email = self.email_input.text().strip()
        password = self.password_input.text().strip()
        key = self.key_input.text().strip()
        
        if not email or not password or not key:
            QMessageBox.warning(self, "Error", "All fields are required.")
            return
            
        self.activate_btn.setText("Authenticating...")
        self.activate_btn.setEnabled(False)
        QApplication.processEvents()
        
        try:
            # Step 1: Login
            req1 = urllib.request.Request(
                f"{API_BASE_URL}/api/agent-auth/login",
                data=json.dumps({"email": email, "password": password}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req1) as response:
                    res1 = json.loads(response.read().decode())
            except urllib.error.HTTPError as e:
                err_data = json.loads(e.read().decode())
                raise Exception(err_data.get("error", "Login failed."))
                
            access_token = res1.get("access_token")
            if not access_token:
                raise Exception("No access token returned.")
                
            # Step 2: Activate
            hwid = get_hardware_id()
            req2 = urllib.request.Request(
                f"{API_BASE_URL}/api/agent-auth/activate",
                data=json.dumps({
                    "licenseKey": key,
                    "deviceId": hwid,
                    "productSlug": self.product_slug
                }).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}"
                }
            )
            
            try:
                with urllib.request.urlopen(req2) as response:
                    res2 = json.loads(response.read().decode())
            except urllib.error.HTTPError as e:
                err_data = json.loads(e.read().decode())
                raise Exception(err_data.get("error", "Activation failed."))
                
            lease = res2.get("lease")
            
            # Decode JWT to get expiration
            parts = lease.split('.')
            if len(parts) >= 2:
                import base64
                payload = parts[1]
                payload += '=' * (-len(payload) % 4)
                decoded = json.loads(base64.b64decode(payload).decode())
                exp = decoded.get("exp", time.time() + (7*24*60*60))
            else:
                exp = time.time() + (7*24*60*60)
                
            save_lease(lease, exp)
            QMessageBox.information(self, "Success", "Agent activated successfully!")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.activate_btn.setText("Activate & Launch")
            self.activate_btn.setEnabled(True)

def require_license(product_slug):
    lease = load_lease()
    if lease:
        return True # Valid lease found
        
    dialog = ActivationDialog(product_slug)
    result = dialog.exec()
    if result == QDialog.Accepted:
        return True
    return False

