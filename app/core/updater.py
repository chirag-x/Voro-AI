import os
import sys
import json
import httpx
import subprocess
import tempfile
import threading
from PySide6.QtCore import QObject, Signal

from app.core.version import APP_VERSION, UPDATE_CHECK_URL
from app.utils.logging import logger

class Updater(QObject):
    update_available = Signal(str, str, str) # version, notes, download_url
    download_progress = Signal(int)
    download_complete = Signal(str)
    download_error = Signal(str)
    check_error = Signal(str)
    no_update = Signal()

    def __init__(self):
        super().__init__()
        self.is_downloading = False

    def check_for_updates(self):
        def _check():
            try:
                r = httpx.get("https://api.github.com/repos/chirag-x/Norvi-Agents/releases", timeout=5.0)
                if r.status_code == 200:
                    releases = r.json()
                    
                    latest = None
                    url = ""
                    notes = ""
                    
                    # Search through releases to find the latest one that contains Voro_Setup.exe
                    for release in releases:
                        assets = release.get("assets", [])
                        voro_asset = next((a for a in assets if "Voro_Setup.exe" in a.get("name", "")), None)
                        
                        if voro_asset:
                            # We found the latest Voro release!
                            latest = release.get("tag_name", "").replace("voro-", "").lstrip("v")
                            url = voro_asset["browser_download_url"]
                            notes = release.get("body", "")
                            break
                    
                    if latest and self._is_newer(latest, APP_VERSION):
                        self.update_available.emit(latest, notes, url)
                    else:
                        self.no_update.emit()
                else:
                    self.check_error.emit(f"HTTP {r.status_code}")
            except Exception as e:
                logger.error(f"[updater] Check failed: {e}")
                self.check_error.emit(str(e))
        threading.Thread(target=_check, daemon=True).start()

    def _is_newer(self, remote: str, local: str) -> bool:
        def parse(v): return tuple(map(int, v.strip('v').split('.')))
        try:
            return parse(remote) > parse(local)
        except Exception:
            return False

    def download_and_install(self, download_url: str):
        if self.is_downloading: return
        self.is_downloading = True
        
        def _download():
            try:
                temp_dir = tempfile.gettempdir()
                installer_path = os.path.join(temp_dir, "Voro_Update.exe")
                
                with httpx.stream("GET", download_url, follow_redirects=True) as r:
                    r.raise_for_status()
                    total = int(r.headers.get("content-length", 0))
                    downloaded = 0
                    
                    with open(installer_path, "wb") as f:
                        for chunk in r.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                progress = int((downloaded / total) * 100)
                                self.download_progress.emit(progress)
                                
                self.download_complete.emit(installer_path)
                
                # Launch installer silently and quit
                subprocess.Popen([installer_path, "/SILENT"])
                os._exit(0)
                
            except Exception as e:
                logger.error(f"[updater] Download failed: {e}")
                self.download_error.emit(str(e))
                self.is_downloading = False
                
        threading.Thread(target=_download, daemon=True).start()
