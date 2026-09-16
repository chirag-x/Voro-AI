import numpy as np
from threading import Lock

class AudioBuffer:
    """
    A bounded buffer for audio chunks.
    Prevents infinite memory growth and allows reading chunks.
    """
    def __init__(self, max_chunks: int = 100):
        self.max_chunks = max_chunks
        self.buffer = []
        self.lock = Lock()

    def add_chunk(self, chunk: np.ndarray):
        """Add an audio chunk to the buffer."""
        with self.lock:
            if len(self.buffer) >= self.max_chunks:
                # Drop oldest chunk if buffer is full
                self.buffer.pop(0)
            self.buffer.append(chunk)

    def get_chunks(self) -> list:
        """Retrieve all current chunks and clear the buffer."""
        with self.lock:
            chunks = self.buffer.copy()
            self.buffer.clear()
            return chunks

    def clear(self):
        """Clear all chunks from the buffer."""
        with self.lock:
            self.buffer.clear()

    def __len__(self):
        with self.lock:
            return len(self.buffer)
