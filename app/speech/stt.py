import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

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
    def __init__(self, model_size: str = "tiny.en", device: str = "cpu", compute_type: str = "int8", model_dir: str = "", groq_api_key: str = ""):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model_dir = model_dir
        self.groq_api_key = groq_api_key
        self.model = None

    def initialize(self, force=False):
        """Initialize and load the model."""
        if self.groq_api_key and self.groq_api_key.strip() and not force:
            logger.info("Groq API key found. Skipping local model load (will lazy-load if fallback is needed).")
            return
            
        logger.info(f"Loading STT model '{self.model_size}' on {self.device}...")
        
        # Default to a local directory if none is set
        if not self.model_dir or not self.model_dir.strip():
            self.model_dir = os.path.join(os.getcwd(), "STT_models")
            
        os.makedirs(self.model_dir, exist_ok=True)
            
        model_path = os.path.join(self.model_dir.strip(), f"faster-whisper-{self.model_size}")
        if not os.path.exists(model_path):
            logger.warning(f"STT model '{self.model_size}' not found in '{model_path}'. Please download it via Settings.")
            return
        
        start = time.time()
        
        # Determine compute type based on device
        if self.compute_type == "int8" and self.device == "cuda":
            self.compute_type = "float16" # Usually better for GPU
            
        try:
            self.model = WhisperModel(
                model_path, 
                device=self.device, 
                compute_type=self.compute_type,
                cpu_threads=4,
                local_files_only=True
            )
        except Exception as e:
            if self.device == "cuda":
                logger.warning(f"Failed to load on CUDA: {e}. Falling back to CPU...")
                self.device = "cpu"
                self.compute_type = "int8"
                self.model = WhisperModel(
                    model_path, 
                    device=self.device, 
                    compute_type=self.compute_type,
                cpu_threads=4,
                    local_files_only=True
                )
            else:
                raise
                
        logger.info(f"STT model loaded in {time.time() - start:.2f}s")

    def transcribe(self, audio_segment: np.ndarray, sample_rate: int = 16000, **kwargs) -> TranscriptResult:
        """
        Transcribe an audio segment.
        The audio_segment is expected to be a 1D numpy array of float32.
        """
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

        text = ""
        info = None
        local_run = True

        if self.groq_api_key and self.groq_api_key.strip():
            try:
                import io
                import wave
                import httpx
                
                audio_data = np.clip(audio_segment, -1.0, 1.0)
                audio_data = (audio_data * 32767.0).astype(np.int16)
                
                wav_io = io.BytesIO()
                with wave.open(wav_io, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_data.tobytes())
                wav_io.seek(0)
                
                logger.info("[stt] Attempting turbo transcription via Groq API...")
                
                headers = {"Authorization": f"Bearer {self.groq_api_key.strip()}"}
                files = {"file": ("audio.wav", wav_io.read(), "audio/wav")}
                data = {
                    "model": "whisper-large-v3-turbo",
                    "temperature": "0.0"
                }
                
                if is_en_only:
                    data["language"] = "en"
                
                if kwargs.get("initial_prompt"):
                    data["prompt"] = kwargs.get("initial_prompt")
                
                with httpx.Client(timeout=4.0) as client:
                    resp = client.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers=headers,
                        data=data,
                        files=files
                    )
                    resp.raise_for_status()
                    
                result_json = resp.json()
                text = result_json.get("text", "").strip()
                
                class DummyInfo:
                    language = "en"
                    language_probability = 1.0
                    duration = len(audio_segment) / sample_rate
                info = DummyInfo()
                
                logger.info(f"[stt] Groq transcription successful in {time.time() - start_time:.2f}s")
                local_run = False
                
            except Exception as e:
                logger.warning(f"[stt] Groq API failed ({type(e).__name__}: {e}). Falling back to local faster-whisper...")
                local_run = True

        try:
            if local_run:
                if self.model is None:
                    logger.info("Initializing local STT fallback model (lazy-load)...")
                    self.initialize(force=True)
                    if self.model is None:
                        raise RuntimeError("Local STT model is not downloaded. Please download it in Settings.")
                    
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
                model_path = os.path.join(self.model_dir.strip(), f'faster-whisper-{self.model_size}')
                self.model = WhisperModel(
                    model_path,
                    device=self.device,
                    compute_type=self.compute_type,
                    cpu_threads=4
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
            
            # Drop famous Whisper silence hallucinations
            lower_txt = text.lower().strip()
            hallucinations = [
                "thank you", "thank you.", "thank you!", 
                "thank you so much for joining us", "thank you so much for joining us.",
                "thank you for joining us", "thank you for joining us.",
                "thank you for watching", "thank you for watching.",
                "thanks for watching", "thanks for watching.",
                "amara.org", "amara.org."
            ]
            if lower_txt in hallucinations:
                text = ""
                
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
