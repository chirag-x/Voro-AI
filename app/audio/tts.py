import os
import time
import asyncio
import threading
import queue
from app.utils.logging import logger
import edge_tts

class TTSWorker(threading.Thread):
    def __init__(self, audio_ready_callback, config):
        super().__init__(daemon=True)
        self.audio_ready_callback = audio_ready_callback
        self.config = config
        self.queue = queue.Queue()
        self.running = True
        self.voice = "en-US-AriaNeural"
        
        self.temp_dir = os.path.join(os.getcwd(), "temp_tts")
        os.makedirs(self.temp_dir, exist_ok=True)
        self._clear_temp()

    def _clear_temp(self):
        for f in os.listdir(self.temp_dir):
            if f.endswith(".mp3"):
                try:
                    os.remove(os.path.join(self.temp_dir, f))
                except:
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
                
                rate = getattr(self.config, 'ui_tts_rate', '+0%')
                communicate = edge_tts.Communicate(text, self.voice, rate=rate)
                loop.run_until_complete(communicate.save(filepath))
                
                if os.path.exists(filepath):
                    self.audio_ready_callback(filepath)
            except Exception as e:
                logger.error(f"[tts] Generation failed: {e}")

    def shutdown(self):
        self.running = False
        self.queue.put("STOP")
