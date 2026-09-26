import os
import sys
import shutil
import subprocess
import threading
import urllib.request
import time
import atexit
from app.utils.logging import logger

OLLAMA_MODEL = "gemma4:cloud"

class OllamaManager:
    def __init__(self):
        self.process = None
        self.running = True
        self.watchdog_thread = None

    def _get_ollama_path(self):
        ollama_path = shutil.which("ollama")
        if not ollama_path:
            local_app_data = os.environ.get("LOCALAPPDATA", "")
            alt_path = os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe")
            if os.path.exists(alt_path):
                ollama_path = alt_path
        return ollama_path

    def _is_model_pulled(self, ollama_path):
        try:
            result = subprocess.run([ollama_path, "list"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return OLLAMA_MODEL in result.stdout
        except Exception:
            return False

    def _is_process_running(self):
        try:
            result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ollama.exe", "/NH"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return "ollama.exe" in result.stdout
        except Exception:
            return False

    def check_and_start(self):
        def _task():
            ollama_path = self._get_ollama_path()
            
            # 1. Download and install if missing
            if not ollama_path:
                logger.info("Ollama not found. Downloading installer...")
                installer_path = os.path.join(os.environ["TEMP"], "OllamaSetup.exe")
                try:
                    urllib.request.urlretrieve("https://ollama.com/download/OllamaSetup.exe", installer_path)
                    logger.info("Installing Ollama (UAC prompt may appear)...")
                    subprocess.run([installer_path], check=True)
                    time.sleep(3) # Give it a moment to finish installing
                    ollama_path = self._get_ollama_path()
                except Exception as e:
                    logger.error(f"Failed to install Ollama: {e}")
                    return

            if not ollama_path:
                logger.error("Ollama installation failed to verify.")
                return

            # 2. Login & Onboarding (Visible to Invisible)
            if not self._is_model_pulled(ollama_path):
                logger.info(f"Model {OLLAMA_MODEL} not found. Triggering visible login/pull window...")
                # Launch a visible command prompt so the user can login and pull
                # We title it 'Norvi Agent - Ollama Login' so we can kill it specifically later
                visible_cmd = f'start "NorviAgent_OllamaLogin" cmd.exe /c "echo Please log in or wait for the model to download... && {ollama_path} run {OLLAMA_MODEL}"'
                subprocess.Popen(visible_cmd, shell=True)

                # Polling loop: Wait until the model successfully appears in the list (meaning login and pull succeeded)
                while self.running and not self._is_model_pulled(ollama_path):
                    time.sleep(3)
                
                if not self.running:
                    return

                logger.info("Login and pull successful! Hiding window and transitioning to background...")
                # Kill the visible CMD window
                subprocess.run(["taskkill", "/FI", 'WINDOWTITLE eq NorviAgent_OllamaLogin*', "/F"], creationflags=subprocess.CREATE_NO_WINDOW, check=False)

            # 3. Start Watchdog
            self.watchdog_thread = threading.Thread(target=self._watchdog_loop, args=(ollama_path,), daemon=True)
            self.watchdog_thread.start()

        threading.Thread(target=_task, daemon=True).start()

    def _watchdog_loop(self, ollama_path):
        while self.running:
            if not self._is_process_running():
                logger.info("Ollama is not running. Watchdog is silently restarting it...")
                try:
                    self.process = subprocess.Popen([ollama_path, "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
                except Exception as e:
                    logger.error(f"Watchdog failed to start Ollama: {e}")
            time.sleep(5)

    def shutdown(self):
        self.running = False
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
            
        # Bulletproof Hard kill for all ollama processes (tree kill)
        try:
            subprocess.run(["taskkill", "/F", "/T", "/IM", "ollama.exe"], creationflags=subprocess.CREATE_NO_WINDOW, check=False)
        except Exception:
            pass

manager = OllamaManager()
atexit.register(manager.shutdown)
