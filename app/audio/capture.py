import sounddevice as sd
import numpy as np
import threading
from app.core.lifecycle import Lifecycle
from app.audio.buffer import AudioBuffer
from app.utils.logging import logger
from app.utils.errors import AudioError

class AudioCaptureEngine(Lifecycle):
    """
    Captures audio from the microphone and system loopback asynchronously.
    """
    def __init__(self, device_index: int, sample_rate: int, channels: int, chunk_size: int):
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        
        self.buffer = AudioBuffer(max_chunks=200) # Roughly 20 seconds at 1024 chunk / 16kHz
        self.stream = None
        self._is_running = False
        
        # Loopback properties
        self._loopback_chunk = np.zeros((self.chunk_size, self.channels), dtype='float32')
        self._loopback_thread = None

    def initialize(self) -> None:
        """Initialize the audio streams."""
        try:
            self.stream = sd.InputStream(
                device=self.device_index,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32',
                blocksize=self.chunk_size,
                callback=self._audio_callback
            )
        except Exception as e:
            raise AudioError(f"Failed to initialize audio stream: {e}")

    def _loopback_worker(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                import soundcard as sc
                speaker = sc.default_speaker()
                mics = sc.all_microphones(include_loopback=True)
                loopback_mic = next((m for m in mics if m.isloopback and m.name == speaker.name), None)
                
                if not loopback_mic:
                    logger.error("[audio] Could not find loopback device for default speaker.")
                    return
                    
                with loopback_mic.recorder(samplerate=self.sample_rate, channels=self.channels) as mic:
                    while self._is_running:
                        # Record a chunk of loopback audio
                        data = mic.record(numframes=self.chunk_size)
                        # soundcard returns float32 numpy array
                        self._loopback_chunk = data
            except Exception as e:
                logger.error(f"[audio] Loopback capture failed: {e}")

    def _audio_callback(self, indata, frames, time, status):
        """Callback invoked by sounddevice for each audio chunk."""
        if status:
            logger.warning(f"Audio stream status: {status}")
            
        if self._is_running:
            # Check flags directly from environment variables (much faster than load_config parsing)
            import os
            mute_mic = os.getenv("MUTE_USER_MIC", "False").lower() == "true"
            mute_sys = os.getenv("MUTE_SYSTEM_AUDIO", "False").lower() == "true"
            
            # Anti-Feedback: Mute User Mic while Voro is actively speaking
            if os.getenv("VORO_IS_SPEAKING", "False") == "True":
                mute_mic = True
            
            # Mix the microphone indata with the latest loopback chunk
            mic_data = np.zeros_like(indata) if mute_mic else indata.copy()
            lb_data = np.zeros_like(self._loopback_chunk) if mute_sys else self._loopback_chunk.copy()
            
            # Ensure shapes match (fallback if something goes wrong)
            if lb_data.shape != mic_data.shape:
                if len(lb_data.shape) > 1 and lb_data.shape[1] > mic_data.shape[1]:
                    lb_data = np.mean(lb_data, axis=1, keepdims=True)
                elif len(mic_data.shape) > 1 and mic_data.shape[1] > lb_data.shape[1]:
                    mic_data = np.mean(mic_data, axis=1, keepdims=True)
                try:
                    lb_data = lb_data.reshape(mic_data.shape)
                except:
                    lb_data = np.zeros_like(mic_data)
                
            # We now push a tuple of (Mic, System) instead of a mixed track
            # for Speaker Diarization.
            self.buffer.add_chunk((mic_data, lb_data))

    def start(self) -> None:
        """Start capturing audio."""
        if not self.stream:
            raise AudioError("Stream not initialized.")
            
        if not self._is_running:
            self.buffer.clear()
            self._is_running = True
            
            # Start loopback thread
            self._loopback_thread = threading.Thread(target=self._loopback_worker, daemon=True)
            self._loopback_thread.start()
            
            try:
                self.stream.start()
            except Exception as e:
                self._is_running = False
                raise AudioError(f"Failed to start audio stream: {e}")

    def stop(self) -> None:
        """Stop capturing audio."""
        if self._is_running and self.stream:
            self._is_running = False
            self.stream.stop()
            logger.info("Audio capture stopped")

    def is_running(self) -> bool:
        return self._is_running

    def shutdown(self) -> None:
        """Close the stream completely."""
        self.stop()
        if self.stream:
            self.stream.close()
            self.stream = None
