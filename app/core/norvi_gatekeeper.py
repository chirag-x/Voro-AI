import os
import sys
import json
import time
import uuid
import platform
import ssl
import urllib.request
import urllib.error
from app.utils.logging import logger
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QApplication
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt

API_BASE_URL = os.getenv("NORVI_API_URL", "https://nor-vi.in")
LEASE_FILE = os.path.join(os.path.expanduser("~"), ".norvi_voro_lease")

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    path = os.path.join(base_path, relative_path)
    if not os.path.exists(path) and os.path.exists(relative_path):
        return os.path.abspath(relative_path)
    return path

def _is_dark_mode():
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return val == 0
    except Exception:
        return True

def _safe_urlopen(req, timeout=10.0):
    """
    Executes an HTTPS request using an up-to-date CA bundle (certifi).
    If certificate verification fails due to client system clock drift or
    expired local root trust stores (e.g. DST Root CA X3 on Windows),
    it automatically falls back to an unverified context so valid customers
    are never locked out.
    """
    try:
        import certifi
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ssl_ctx = ssl.create_default_context()
        
    try:
        return urllib.request.urlopen(req, context=ssl_ctx, timeout=timeout)
    except urllib.error.URLError as e:
        reason_str = str(getattr(e, 'reason', e))
        if "CERTIFICATE_VERIFY_FAILED" in reason_str or "certificate has expired" in reason_str or "certificate verify failed" in reason_str:
            logger.warning(f"SSL certificate verification failed ({reason_str}). Retrying with fallback SSL context...")
            fallback_ctx = ssl._create_unverified_context()
            return urllib.request.urlopen(req, context=fallback_ctx, timeout=timeout)
        raise

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

def save_lease(token, expires_at, license_key=None, plan_expires_at=None):
    try:
        data = {
            "token": token,
            "expires_at": expires_at,
            "last_verified_at": time.time()
        }
        if license_key:
            data["license_key"] = license_key
        if plan_expires_at is not None:
            data["plan_expires_at"] = plan_expires_at
        elif os.path.exists(LEASE_FILE):
            try:
                with open(LEASE_FILE, 'r') as f:
                    old_data = json.load(f)
                    if "plan_expires_at" in old_data:
                        data["plan_expires_at"] = old_data["plan_expires_at"]
            except Exception:
                pass
        with open(LEASE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Failed to save lease: {e}")

def verify_online_lease(product_slug="voro"):
    """
    Silently checks license validity with the Norvi backend everyday.
    Returns (success: bool, error_message: str | None).
    If the license has been revoked or expired, removes local lease and returns False.
    """
    if not os.path.exists(LEASE_FILE):
        return False, "No active lease found."

    try:
        with open(LEASE_FILE, 'r') as f:
            data = json.load(f)
    except Exception:
        return False, "Could not read local lease."

    token = data.get("token")
    license_key = data.get("license_key")
    hwid = get_hardware_id()

    payload = {
        "deviceId": hwid,
        "productSlug": product_slug
    }
    if token:
        payload["lease"] = token
    if license_key:
        payload["licenseKey"] = license_key

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        f"{API_BASE_URL}/api/agent-auth/verify",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers
    )

    try:
        with _safe_urlopen(req, timeout=8.0) as response:
            res = json.loads(response.read().decode())
            new_lease = res.get("lease")
            plan_expires_at = res.get("expires_at")
            if not new_lease:
                return False, "Server returned no lease."

            # Decode JWT to get expiration
            parts = new_lease.split('.')
            exp = time.time() + (24 * 60 * 60)
            if len(parts) >= 2:
                import base64
                payload_part = parts[1]
                payload_part += '=' * (-len(payload_part) % 4)
                decoded = json.loads(base64.b64decode(payload_part).decode())
                exp = decoded.get("exp", exp)

            save_lease(new_lease, exp, license_key=license_key or data.get("license_key"), plan_expires_at=plan_expires_at)
            logger.info("Daily license validity check succeeded.")
            return True, None

    except urllib.error.HTTPError as e:
        try:
            err_data = json.loads(e.read().decode())
            msg = err_data.get("error", "License verification failed.")
            is_terminal = err_data.get("deactivated") or err_data.get("expired") or err_data.get("blocked") or e.code in (401, 403, 404)
        except Exception:
            msg = f"HTTP Error {e.code}"
            is_terminal = e.code in (401, 403, 404)

        if is_terminal:
            try:
                if os.path.exists(LEASE_FILE):
                    os.remove(LEASE_FILE)
            except Exception:
                pass
            return False, msg
        return False, msg

    except Exception as e:
        logger.warning(f"Could not connect to verification server: {e}")
        # Offline resilience: allow temporary use if within 24 hours of last successful verification
        last_verified = data.get("last_verified_at", 0)
        expires_at = data.get("expires_at", 0)
        now = time.time()
        if now <= expires_at and (now - last_verified) < (24 * 60 * 60):
            return True, None
        return False, "Internet connection required to verify daily license validity."

class ActivationDialog(QDialog):
    def __init__(self, product_slug, parent=None, initial_error=None):
        super().__init__(parent)
        self.product_slug = product_slug
        self.initial_error = initial_error
        self.setWindowTitle("NORVI Activation")
        self.setFixedSize(420, 480)
        
        is_dark = _is_dark_mode()
        bg_col = "#181818" if is_dark else "#F8F9FA"
        fg_col = "#FFFFFF" if is_dark else "#1A1A1A"
        subtext_col = "#AAAAAA" if is_dark else "#555555"
        input_bg = "#242424" if is_dark else "#FFFFFF"
        input_border = "#383838" if is_dark else "#D0D0D0"
        btn_bg = "#16A34A"
        btn_hover = "#15803D"
        error_col = "#EF4444" if is_dark else "#DC2626"
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_col};
                color: {fg_col};
            }}
            QMessageBox {{
                background-color: {bg_col};
                color: {fg_col};
            }}
            QMessageBox QLabel {{
                color: {fg_col};
            }}
        """)
        
        logo_file = resource_path("norvi_logo.png")
        if os.path.exists(logo_file):
            self.setWindowIcon(QIcon(logo_file))
            
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(10)
        
        if os.path.exists(logo_file):
            logo_pix = QPixmap(logo_file)
            if not logo_pix.isNull():
                logo_lbl = QLabel()
                logo_lbl.setPixmap(logo_pix.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                logo_lbl.setAlignment(Qt.AlignCenter)
                layout.addWidget(logo_lbl)
        
        title = QLabel("Agent Activation")
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {fg_col}; margin-top: 2px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        desc_text = f"Please log in to your NORVI account and enter your activation key for {product_slug.capitalize()}."
        if self.initial_error:
            desc_text = f"{self.initial_error}\n\nPlease enter your NORVI credentials and activation key to continue."
            
        desc = QLabel(desc_text)
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc_color = error_col if self.initial_error else subtext_col
        desc.setStyleSheet(f"color: {desc_color}; font-size: 12px; margin-bottom: 8px;")
        layout.addWidget(desc)
        
        input_qss = f"padding: 10px; border: 1px solid {input_border}; border-radius: 5px; background: {input_bg}; color: {fg_col}; font-size: 13px;"
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("NORVI Email")
        self.email_input.setStyleSheet(input_qss)
        layout.addWidget(self.email_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet(input_qss)
        layout.addWidget(self.password_input)
        
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Activation Key (e.g., NORVI-XXXX-...)")
        self.key_input.setStyleSheet(f"{input_qss} margin-bottom: 10px;")
        layout.addWidget(self.key_input)
        
        self.activate_btn = QPushButton("Activate && Launch")
        self.activate_btn.setCursor(Qt.PointingHandCursor)
        self.activate_btn.setStyleSheet(f"QPushButton {{ padding: 12px; background-color: {btn_bg}; color: white; border: none; border-radius: 5px; font-weight: bold; font-size: 14px; }} QPushButton:hover {{ background-color: {btn_hover}; }}")
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
            with _safe_urlopen(req1, timeout=10.0) as response:
                res1 = json.loads(response.read().decode())
                
            access_token = res1.get("access_token")
            if not access_token:
                raise Exception("No access token returned from login.")
                
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
            
            with _safe_urlopen(req2, timeout=10.0) as response:
                res2 = json.loads(response.read().decode())
                
            lease = res2.get("lease")
            plan_expires_at = res2.get("expires_at")
            if not lease:
                raise Exception("No lease token returned from server.")
            
            # Decode JWT to get expiration (24h default)
            parts = lease.split('.')
            exp = time.time() + (24 * 60 * 60)
            if len(parts) >= 2:
                import base64
                payload = parts[1]
                payload += '=' * (-len(payload) % 4)
                decoded = json.loads(base64.b64decode(payload).decode())
                exp = decoded.get("exp", exp)
                
            save_lease(lease, exp, license_key=key, plan_expires_at=plan_expires_at)
            QMessageBox.information(self, "Success", "Agent activated successfully!")
            self.accept()
            
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode())
                msg = err_data.get("error", f"Request failed: HTTP {e.code}")
            except Exception:
                msg = f"HTTP Error {e.code}"
            QMessageBox.critical(self, "Activation Error", msg)
            self.activate_btn.setText("Activate && Launch")
            self.activate_btn.setEnabled(True)
        except urllib.error.URLError as e:
            QMessageBox.critical(self, "Connection Error", f"Could not reach activation server: {e.reason}")
            self.activate_btn.setText("Activate && Launch")
            self.activate_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.activate_btn.setText("Activate && Launch")
            self.activate_btn.setEnabled(True)

def require_license(product_slug):
    lease = load_lease()
    err_message = None

    if lease:
        last_verified = lease.get("last_verified_at", 0)
        now = time.time()
        # Daily check: if more than 24 hours since last verification or approaching expiry
        if (now - last_verified) >= (24 * 60 * 60) or now >= lease.get("expires_at", 0):
            ok, err_message = verify_online_lease(product_slug)
            if ok:
                return True
            logger.warning(f"Daily license check failed: {err_message}")
        else:
            return True # Valid within 24 hours

    dialog = ActivationDialog(product_slug, initial_error=err_message)
    result = dialog.exec()
    if result == QDialog.Accepted:
        return True
    return False
