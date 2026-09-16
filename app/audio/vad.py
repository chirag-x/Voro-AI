import webrtcvad
import numpy as np
from typing import List, Optional
from enum import Enum
import collections

class VadState(Enum):
    SILENCE = 0
    SPEECH = 1

class VadEvent(Enum):
    SPEECH_STARTED = 1
    SPEECH_ENDED = 2

class VadEngine:
    """
    Voice Activity Detection subsystem using webrtcvad.
    Processes audio chunks to detect speech segments.
    """
    def __init__(self, sample_rate: int = 16000, aggressiveness: int = 2):
        self.sample_rate = sample_rate
        self.vad = webrtcvad.Vad(aggressiveness)
        
        # Webrtcvad needs 10, 20, or 30ms frames. We'll use 30ms.
        self.frame_duration_ms = 30
        self.frame_length = int(sample_rate * (self.frame_duration_ms / 1000.0)) # 480 for 16kHz
        
        self.state = VadState.SILENCE
        self._audio_buffer = np.array([], dtype=np.float32)
        
        # State tracking
        self.triggered = False
        
        # Smoothing (require multiple frames to switch states)
        self.padding_duration_ms = 150
        self.num_padding_frames = int(self.padding_duration_ms / self.frame_duration_ms)
        self.ring_buffer = collections.deque(maxlen=self.num_padding_frames)
        
        self.current_speech_segment = []

    def process_chunk(self, chunk: np.ndarray) -> List[tuple[VadEvent, Optional[np.ndarray]]]:
        """
        Process an incoming float32 audio chunk and return a list of VAD events.
        """
        events = []
        # Ensure chunk is 1D (e.g. if it comes in as (1024, 1) from sounddevice)
        chunk = chunk.flatten()
        self._audio_buffer = np.concatenate((self._audio_buffer, chunk))
        
        while len(self._audio_buffer) >= self.frame_length:
            frame = self._audio_buffer[:self.frame_length]
            self._audio_buffer = self._audio_buffer[self.frame_length:]
            
            # Convert float32 [-1, 1] to int16 bytes
            pcm_data = (frame * 32767).astype(np.int16).tobytes()
            is_speech = self.vad.is_speech(pcm_data, self.sample_rate)
            
            self.ring_buffer.append((frame, is_speech))
            
            if not self.triggered:
                num_voiced = len([f for f, speech in self.ring_buffer if speech])
                if num_voiced > 0.9 * self.ring_buffer.maxlen:
                    self.triggered = True
                    events.append((VadEvent.SPEECH_STARTED, None))
                    # Keep the padding before speech started
                    for f, s in self.ring_buffer:
                        self.current_speech_segment.append(f)
                    self.ring_buffer.clear()
            else:
                self.current_speech_segment.append(frame)
                num_unvoiced = len([f for f, speech in self.ring_buffer if not speech])
                if num_unvoiced > 0.9 * self.ring_buffer.maxlen:
                    self.triggered = False
                    # Emit speech segment
                    segment = np.concatenate(self.current_speech_segment)
                    events.append((VadEvent.SPEECH_ENDED, segment))
                    self.current_speech_segment = []
                    self.ring_buffer.clear()
                    
        return events

    def reset(self):
        """Clean reset of the VAD state."""
        self.state = VadState.SILENCE
        self.triggered = False
        self._audio_buffer = np.array([], dtype=np.float32)
        self.ring_buffer.clear()
        self.current_speech_segment = []
