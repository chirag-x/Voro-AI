import os
import time
import asyncio
import threading
import queue
import subprocess
import base64
from app.utils.logging import logger
import edge_tts

def _synthesize_local_sapi(text: str, output_wav: str) -> bool:
    """
    Offline fallback TTS using Windows built-in SpeechSynthesizer.
    Guarantees audio generation even when Microsoft Edge TTS cloud is unavailable or blocked.
    """
    try:
        clean_text = text.replace('"', '`"').replace("'", "''")
        clean_path = output_wav.replace('"', '`"').replace("'", "''")
        ps_script = (
            "Add-Type -AssemblyName System.Speech; "
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$synth.SetOutputToWaveFile('{clean_path}'); "
            f"$synth.Speak('{clean_text}'); "
            "$synth.Dispose();"
        )
        encoded_cmd = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_cmd],
            capture_output=True,
            timeout=8,
            startupinfo=startupinfo
        )
        return res.returncode == 0 and os.path.exists(output_wav) and os.path.getsize(output_wav) > 0
    except Exception as e:
        logger.warning(f"[tts] Local SAPI fallback failed: {e}")
        return False

class TTSWorker(threading.Thread):
    def __init__(self, audio_ready_callback, config):
        super().__init__(daemon=True)
        self.audio_ready_callback = audio_ready_callback
        self.config = config
        self.queue = queue.Queue()
        self.running = True
        self.voice = getattr(self.config, 'ui_voice', 'en-US-AriaNeural')
        self.rate = getattr(self.config, 'ui_tts_rate', '+0%')
        
        self.temp_dir = os.path.join(os.environ.get('TEMP', os.getcwd()), "Voro_TTS")
        os.makedirs(self.temp_dir, exist_ok=True)
        self._clear_temp()

    def set_voice(self, voice: str):
        if voice:
            self.voice = voice
            logger.info(f"[tts] Voice updated to: {self.voice}")

    def set_rate(self, rate: str):
        if rate:
            self.rate = rate
            logger.info(f"[tts] Speech rate updated to: {self.rate}")

    def _clear_temp(self):
        for f in os.listdir(self.temp_dir):
            if f.endswith(".mp3") or f.endswith(".wav"):
                try:
                    os.remove(os.path.join(self.temp_dir, f))
                except Exception:
                    pass

    def enqueue(self, text: str):
        if not text.strip(): return
        self.queue.put(text)

    def stop_and_clear(self):
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        chunk_id = 0
        while self.running:
            try:
                text = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue
                
            if text == "STOP":
                break
                
            try:
                filepath = os.path.join(self.temp_dir, f"chunk_{chunk_id}_{int(time.time())}.mp3")
                chunk_id += 1
                
                rate = getattr(self, 'rate', getattr(self.config, 'ui_tts_rate', '+0%'))
                try:
                    communicate = edge_tts.Communicate(text, self.voice, rate=rate)
                    loop.run_until_complete(communicate.save(filepath))
                except Exception as edge_err:
                    logger.warning(f"[tts] Edge TTS failed ({edge_err}). Falling back to local Windows SAPI...")
                    wav_path = filepath.replace(".mp3", ".wav")
                    if _synthesize_local_sapi(text, wav_path):
                        filepath = wav_path
                    else:
                        raise edge_err
                
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    self.audio_ready_callback(filepath)
            except Exception as e:
                logger.error(f"[tts] Generation failed: {e}")

    def shutdown(self):
        self.running = False
        self.queue.put("STOP")
