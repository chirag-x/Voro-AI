import time
import numpy as np
from faster_whisper import WhisperModel
from app.speech.models import TranscriptResult
from app.utils.logging import logger

class SpeechToText:
    """
    Speech-to-text engine using faster-whisper.
    Provides a clean abstraction so the rest of the application
    does not depend directly on whisper implementation details.
    """
    def __init__(self, model_size: str = "tiny.en", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None

    def initialize(self):
        """Initialize and load the model."""
        logger.info(f"Loading STT model '{self.model_size}' on {self.device}...")
        start = time.time()
        
        # Determine compute type based on device
        if self.compute_type == "int8" and self.device == "cuda":
            self.compute_type = "float16" # Usually better for GPU
            
        try:
            self.model = WhisperModel(
                self.model_size, 
                device=self.device, 
                compute_type=self.compute_type
            )
        except Exception as e:
            if self.device == "cuda":
                logger.warning(f"Failed to load on CUDA: {e}. Falling back to CPU...")
                self.device = "cpu"
                self.compute_type = "int8"
                self.model = WhisperModel(
                    self.model_size, 
                    device=self.device, 
                    compute_type=self.compute_type
                )
            else:
                raise
                
        logger.info(f"STT model loaded in {time.time() - start:.2f}s")

    def transcribe(self, audio_segment: np.ndarray, sample_rate: int = 16000, **kwargs) -> TranscriptResult:
        """
        Transcribe an audio segment.
        The audio_segment is expected to be a 1D numpy array of float32.
        """
        if self.model is None:
            raise RuntimeError("STT engine not initialized.")
            
        start_time = time.time()
        
        # We always check if we're using English specific model or multilingual
        is_en_only = self.model_size.endswith(".en")
        
        def run_transcribe(audio, lang):
            segs, inf = self.model.transcribe(
                audio, 
                beam_size=5,
                vad_filter=False,
                language=lang,
                task="transcribe",
                initial_prompt=kwargs.get("initial_prompt", None)
            )
            # Force evaluation of the generator to catch lazy CUDA errors
            out_text = " ".join([seg.text for seg in segs]).strip()
            return out_text, inf

        try:
            target_lang = "en" if is_en_only else None
            text, info = run_transcribe(audio_segment, target_lang)
            
            # If the model hallucinates a random language (e.g. Portuguese) instead of English/Hindi
            if not is_en_only and info.language not in ["en", "hi"]:
                logger.info(f"[stt] Whisper guessed random language '{info.language}'. Forcing Hindi transcription...")
                text, info = run_transcribe(audio_segment, "hi")

        except RuntimeError as e:
            err_str = str(e)
            if "Library cublas" in err_str or "cudnn" in err_str or "CUDA" in err_str:
                logger.warning(f"CUDA inference failed ({err_str}). Falling back to CPU permanently...")
                self.device = "cpu"
                self.compute_type = "int8"
                self.model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type
                )
                
                # Retry on CPU
                target_lang = "en" if is_en_only else None
                text, info = run_transcribe(audio_segment, target_lang)
                
                if not is_en_only and info.language not in ["en", "hi"]:
                    logger.info(f"[stt] Whisper guessed random language '{info.language}'. Forcing Hindi transcription...")
                    text, info = run_transcribe(audio_segment, "hi")
            else:
                raise
        
        # Whisper Hallucination Filter
        # Whisper often repeats the `initial_prompt` during silence or breathing
        initial_prompt = kwargs.get("initial_prompt", "")
        if initial_prompt:
            import re
            # Remove exact or near-exact repeats of the prompt
            if "highly technical" in text.lower():
                # If the user happens to say "highly technical", we might lose it, but it's very rare.
                # Let's just aggressively filter known chunks.
                for chunk in [
                    "This is a highly technical software engineering interview",
                    "This is a highly technical software engineering.",
                    "This is a highly technical software engineering",
                    "highly technical software engineering interview",
                    "covering programming, system design, and coding",
                    "system design, and coding",
                    "This is a highly technical"
                ]:
                    # Case insensitive replace
                    pattern = re.compile(re.escape(chunk), re.IGNORECASE)
                    text = pattern.sub("", text)
            
            text = text.strip()
            
            # If after stripping the prompt, what remains is tiny or empty, just drop it
            if len(text) < 3 or (len(set(text.lower().split()) - set(initial_prompt.lower().split())) <= 1):
                text = ""
        
        processing_time = time.time() - start_time
        
        return TranscriptResult(
            text=text,
            language=info.language,
            confidence=info.language_probability,
            duration=info.duration,
            processing_time=processing_time
        )
