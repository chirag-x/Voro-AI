<<<<<<< HEAD
import os
=======
﻿import os
>>>>>>> 28fda911af64f70a4206de477a70afb6ecbb8a80
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
                r = httpx.get(UPDATE_CHECK_URL, timeout=5.0)
                if r.status_code == 200:
                    data = r.json()
                    latest = data.get("latest_version")
                    url = data.get("download_url")
                    notes = data.get("release_notes", "")
                    
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
<<<<<<< HEAD
        except Exception:
=======
        except:
>>>>>>> 28fda911af64f70a4206de477a70afb6ecbb8a80
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
