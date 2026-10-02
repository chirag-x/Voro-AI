import os
import time
import httpx
import shutil
import urllib.request
import subprocess
import threading
from app.utils.logging import logger

class OllamaManager:
    """Manages Ollama installation, background service, and model pulling."""
    def __init__(self, target_model: str = "gemma4:cloud"):
        self.target_model = target_model
        self.base_url = "http://localhost:11434"
        self.installer_url = "https://ollama.com/download/OllamaSetup.exe"
        self.is_ready = False
        
    def start_setup_thread(self, callback=None):
        """Run the setup process in the background so it doesn't block the UI."""
        def worker():
            try:
                self.ensure_setup()
                self.is_ready = True
                if callback:
                    callback(True, "Ollama is ready and model is pulled.")
            except Exception as e:
                logger.error(f"[OllamaManager] Setup failed: {e}")
                if callback:
                    callback(False, str(e))
                    
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        return t

    def ensure_setup(self):
        """Main flow: check if running, install if missing, pull model."""
        if not self.is_running():
            logger.info("[OllamaManager] Ollama is not responding on port 11434.")
            
            # Check if it's installed but just not running
            local_app_data = os.environ.get('LOCALAPPDATA', '')
            ollama_exe = os.path.join(local_app_data, 'Programs', 'Ollama', 'ollama.exe')
            
            if os.path.exists(ollama_exe):
                logger.info("[OllamaManager] Found Ollama installation. Starting background service...")
                subprocess.Popen([ollama_exe, "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
                self._wait_for_service()
            else:
                logger.info("[OllamaManager] Ollama not found on system. Initiating automated download and install...")
                self._download_and_install()
                
        # Now it should be running. Check for the target model.
        if not self._has_model(self.target_model):
            logger.info(f"[OllamaManager] Model '{self.target_model}' not found. Pulling now (this may take a while)...")
            self._pull_model(self.target_model)
        else:
            logger.info(f"[OllamaManager] Model '{self.target_model}' is already available.")
            
    def is_running(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/", timeout=2.0)
            return r.status_code == 200
        except httpx.RequestError:
            return False

    def _wait_for_service(self, timeout=30):
        start = time.time()
        while time.time() - start < timeout:
            if self.is_running():
                return
            time.sleep(1)
        raise TimeoutError("Timed out waiting for Ollama service to start.")

    def _download_and_install(self):
        installer_path = os.path.join(os.getcwd(), "OllamaSetup.exe")
        try:
            # Download
            logger.info(f"[OllamaManager] Downloading installer from {self.installer_url}...")
            urllib.request.urlretrieve(self.installer_url, installer_path)
            
            # Install silently
            logger.info("[OllamaManager] Running silent installation...")
            # /S or /SILENT is common for Windows installers, NSIS or InnoSetup
            subprocess.run([installer_path, "/S"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Give it a moment to register and start
            time.sleep(5)
            self._wait_for_service(timeout=60)
            logger.info("[OllamaManager] Installation complete and service is running.")
            
        finally:
            # Cleanup installer
            if os.path.exists(installer_path):
                try:
                    os.remove(installer_path)
                except Exception as e:
                    logger.warning(f"[OllamaManager] Failed to cleanup installer: {e}")

    def _has_model(self, model_name: str) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            r.raise_for_status()
            models = r.json().get('models', [])
            return any(m.get('name') == model_name for m in models)
        except Exception as e:
            logger.warning(f"[OllamaManager] Failed to check tags: {e}")
            return False

    def _pull_model(self, model_name: str):
        # We can use the REST API to pull the model so we don't spawn console windows
        try:
            with httpx.stream("POST", f"{self.base_url}/api/pull", json={"name": model_name}, timeout=None) as response:
                for line in response.iter_lines():
                    if line:
                        # Could parse JSON for progress, but just logging is fine for background
                        pass
            logger.info(f"[OllamaManager] Successfully pulled model: {model_name}")
        except Exception as e:
            logger.error(f"[OllamaManager] Failed to pull model via API: {e}")
            raise
