from app.audio.tts import TTSWorker
import time
import queue
import threading
from app.core.state import ApplicationState
from app.core.config import load_config
from app.utils.logging import logger
from app.utils.errors import VoroError
from app.audio.vad import VadEngine, VadEvent
from app.speech.stt import SpeechToText
from app.session.manager import SessionManager
from app.intent.detector import IntentDetector
from app.ai.openrouter import OpenRouterProvider
from app.context.manager import ContextManager
from app.multimodal.context import MultiModalContextEngine
from app.multimodal.router import IntelligenceRouter
from app.answer.engine import AnswerEngine
from app.screen.capture import ScreenCapture
from app.vision.ocr import OCREngine
from app.vision.analyzer import ScreenAnalyzer
from app.coding.detector import CodingIntelligence
from app.core.models import PipelineRequest, PipelineTrace
import time

class VoroApplication:
    """
    Main orchestration class for the Voro assistant.
    Combines audio, STT, session management, and AI orchestration.
    """
    def __init__(self):
        from app.core.config import load_config
        self.state = ApplicationState.STARTING
        logger.info("Voro starting...")
        
        self.config = load_config()
        self.on_answer_callback = None
        self.on_privacy_status_callback = None
        self.on_mic_status_callback = None
        self.on_ai_status_callback = None
        self.on_user_input_callback = None
        self.on_processing_state_callback = None
        self.on_error_callback = None
        self.on_clear_callback = None
        self.on_quit_callback = None
        self.audio_manager = None
        self.audio_capture = None
        self.vad = None
        self.stt = None
        self.session_manager = SessionManager()
        self.tts_worker = None
        self.intent_detector = IntentDetector()
        self.context_manager = ContextManager()
        self.ai_provider = None
        self.answer_engine = None
        
        # Multimodal pipeline
        self.screen_capture = ScreenCapture()
        self.ocr_engine = OCREngine()
        self.screen_analyzer = ScreenAnalyzer()
        self.coding_detector = CodingIntelligence()
        self.mm_engine = MultiModalContextEngine(self.context_manager)
        self.intelligence_router = IntelligenceRouter()
        
        self.audio_queue = queue.Queue(maxsize=100)
        self.segment_queue = queue.Queue(maxsize=20)
        self.ai_queue = queue.Queue(maxsize=20)
        
        self.latest_request_id = None
        
        # Screen cache
        self._last_screen_hash = None
        self._last_ocr_res = None
        self._last_analysis_res = None
        self._last_coding_res = None
        
        self.vad_thread = None
        self.stt_thread = None
        self.ai_thread = None
        self._pipeline_running = False
        
    def initialize(self):
        """Initialize all subsystems."""
        self.state = ApplicationState.INITIALIZING
        logger.info("Initializing Voro...")
        try:
            self.config = load_config()
            logger.info("Configuration loaded")
            
            self.tts_worker = TTSWorker(self._tts_ready_handler, self.config)
            self.tts_worker.start()
            
            # Initialize Window Privacy/Display Architecture
            from app.platform.windows.privacy import check_privacy_capabilities
            capabilities = check_privacy_capabilities()
            for cap, status in capabilities.items():
                logger.info(f"{cap}: {status}")

            # Initialize Audio Subsystem
            logger.info("Audio subsystem initializing...")
            from app.audio.device import AudioDeviceManager
            from app.audio.capture import AudioCaptureEngine
            
            self.audio_manager = AudioDeviceManager()
            devices = self.audio_manager.list_input_devices()
            logger.info("Available microphones:")
            for d in devices:
                logger.info(f"[{d['index']}] {d['name']}")
                
            devices = self.audio_manager.list_input_devices()
            selected_mic = getattr(self.config, 'user_audio_device', 'Default Windows Input')
            target_device = None
            if selected_mic != 'Default Windows Input':
                target_device = next((d for d in devices if d['name'] == selected_mic), None)
            
            if target_device is None:
                target_device = self.audio_manager.get_default_input_device()
                
            if target_device:
                logger.info(f"Using microphone:\n{target_device['name']}")
                
                self.audio_capture = AudioCaptureEngine(
                    device_index=target_device['index'],
                    sample_rate=self.config.audio_sample_rate,
                    channels=self.config.audio_channels,
                    chunk_size=self.config.audio_chunk_size
                )
                self.audio_capture.initialize()
                logger.info("Audio capture ready.")
            else:
                logger.warning("No microphone detected.")

            # Initialize VADs for Stereo Diarization
            logger.info("VAD initializing...")
            self.mic_vad = VadEngine(sample_rate=self.config.audio_sample_rate)
            self.sys_vad = VadEngine(sample_rate=self.config.audio_sample_rate)
            logger.info("VAD ready.")
            
            # Initialize STT
            logger.info("STT initializing...")
            sz = self.config.stt_model_size
            if sz == 'base.en': sz = 'small.en'
            if sz == 'base': sz = 'small'
            self.stt = SpeechToText(
                model_size=sz,
                device=getattr(self.config, 'stt_device', 'cpu'),
                model_dir=getattr(self.config, 'stt_model_dir', '')
            )
            self.stt.initialize()
            logger.info("STT ready.")
            
            # Initialize AI Provider
            self.reload_ai_provider()

            # Setup UI callbacks are handled by main.py
            
            logger.info("Speech pipeline ready.")

            if hasattr(self, 'on_mic_status_callback') and self.on_mic_status_callback:
                self.on_mic_status_callback("READY")
            if hasattr(self, 'on_ai_status_callback') and self.on_ai_status_callback:
                self.on_ai_status_callback("READY")
            if hasattr(self, 'on_privacy_status_callback') and self.on_privacy_status_callback:
                self.on_privacy_status_callback("IDLE")

            self.state = ApplicationState.READY
            logger.info("Voro READY")
        except Exception as e:
            logger.error(f"Initialization failed: {e}", exc_info=True)
            self.state = ApplicationState.FAILED
            if hasattr(self, 'on_mic_status_callback') and self.on_mic_status_callback:
                self.on_mic_status_callback("ERROR")
            if hasattr(self, 'on_ai_status_callback') and self.on_ai_status_callback:
                self.on_ai_status_callback("ERROR")
            raise

    def switch_model(self, new_model: str):
        """Hot-swap the active AI model at runtime."""
        if self.ai_provider:
            self.ai_provider.switch_model(new_model)
        # Also persist to .env
        from dotenv import set_key
        import os
        env_path = os.path.join(os.getcwd(), ".env")
        set_key(env_path, "OPENROUTER_MODEL", new_model)

    def reload_context(self):
        """Reload user profile / context from disk."""
        if self.context_manager:
            self.context_manager.load()
            logger.info("Application context reloaded from disk.")


    def _tts_ready_handler(self, filepath: str):
        if hasattr(self, 'on_tts_audio_callback') and self.on_tts_audio_callback:
            self.on_tts_audio_callback(filepath)

    def stop_current_task(self):
        """Halts any ongoing AI generation and TTS playback."""
        import uuid
        self.latest_request_id = str(uuid.uuid4())
        self.tts_worker.stop_and_clear()
        if hasattr(self, 'on_tts_stop_callback') and self.on_tts_stop_callback:
            self.on_tts_stop_callback()
        if hasattr(self, 'on_processing_state_callback') and self.on_processing_state_callback:
            self.on_processing_state_callback("Task Stopped.")

    def inject_user_input(self, text: str):
        """Injects text into the pipeline as if the user spoke it (e.g., from OCR)."""
        if not text:
            return
            
        if hasattr(self, 'on_user_input_callback') and self.on_user_input_callback:
            self.on_user_input_callback(text)
        if hasattr(self, 'on_processing_state_callback') and self.on_processing_state_callback:
            self.on_processing_state_callback("Analyzing intent...")
            
        self.session_manager.add_user_turn(text)
        
        intent_res = self.intent_detector.detect(text)
        logger.info(f"[intent] {intent_res.intent.value}")
        
        if intent_res.intent.value == "COMMAND":
            clear_phrases = ["reset session", "clear session", "clear conversation", "clear memory", "clear chat", "wipe memory", "forget everything", "new session", "fresh start"]
            if any(p in intent_res.normalized_text for p in clear_phrases):
                self.session_manager.reset_session()
                if hasattr(self, 'on_clear_callback') and self.on_clear_callback:
                    self.on_clear_callback()
                if hasattr(self, 'on_answer_callback') and self.on_answer_callback:
                    self.on_answer_callback("Session cleared. Memory wiped.")
        else:
            logger.info("[router] Route: AI")
            req = PipelineRequest(text=text, intent=intent_res.intent.value)
            self.latest_request_id = req.request_id
            try:
                self.ai_queue.put(req, timeout=1)
            except queue.Full:
                logger.warning("AI queue full, dropping injected input")
                
    def on_snip_callback(self, image, auto=False):
        """Called by ScreenMonitor or UI when a new screen snapshot is ready."""
        try:
            from app.vision.ocr import OCREngine
            from app.screen.models import ScreenFrame
            
            ocr_engine = OCREngine()
            width, height = image.size
            frame = ScreenFrame(
                image=image, 
                timestamp=time.time(),
                monitor=1,
                width=width,
                height=height
            )
            skip_ocr_flag = getattr(self.config, 'activation_mode', 'basic') == 'premium'
            ocr_result = ocr_engine.extract_text(frame, skip_ocr=skip_ocr_flag)
            
            if self.mm_engine:
                self.mm_engine.update_screen_context(ocr_result, None, None)
                
            if auto:
                # Silently inject a contextual intent so AI knows screen updated
                text = "The screen just updated."
                self.session_manager.add_user_turn(text)
                req = PipelineRequest(text=text, intent="SCREEN_UPDATE")
                self.latest_request_id = req.request_id
                self.ai_queue.put(req, timeout=1)
        except Exception as e:
            logger.error(f"Error in on_snip_callback: {e}")

    def start(self):
        """Start the application and its subsystems."""
        if self.state != ApplicationState.READY:
            logger.warning("Cannot start from state: %s", self.state.name)
            return
            
        self.state = ApplicationState.RUNNING
        logger.info("Voro is running.")
        
        self._pipeline_running = True
        self.vad_thread = threading.Thread(target=self._vad_worker, daemon=True)
        self.stt_thread = threading.Thread(target=self._stt_worker, daemon=True)
        self.ai_thread = threading.Thread(target=self._ai_worker, daemon=True)
        self.vad_thread.start()
        self.stt_thread.start()
        self.ai_thread.start()
        
        if self.audio_capture:
            logger.info("Listening for microphone input...")
            self.audio_capture.start()
            
        from app.core.monitor import ScreenMonitor
        self.screen_monitor = ScreenMonitor(self)
        self.screen_monitor.start()

    def _vad_worker(self):
        logger.info("VAD worker started.")
        while self._pipeline_running:
            try:
                chunks = self.audio_capture.buffer.get_chunks() if self.audio_capture else []
                if not chunks:
                    time.sleep(0.05)
                    continue
                
                for mic_chunk, lb_chunk in chunks:
                    mic_events = self.mic_vad.process_chunk(mic_chunk)
                    for event, data in mic_events:
                        if event == VadEvent.SPEECH_STARTED:
                            logger.info("[vad] User Speech started")
                        elif event == VadEvent.SPEECH_ENDED:
                            logger.info("[vad] User Speech ended")
                            if data is not None:
                                try:
                                    self.segment_queue.put(("You", data), timeout=1)
                                except queue.Full:
                                    logger.warning("Segment queue full, dropping mic segment")
                                    
                    sys_events = self.sys_vad.process_chunk(lb_chunk)
                    for event, data in sys_events:
                        if event == VadEvent.SPEECH_STARTED:
                            logger.info("[vad] Interviewer Speech started")
                        elif event == VadEvent.SPEECH_ENDED:
                            logger.info("[vad] Interviewer Speech ended")
                            if data is not None:
                                try:
                                    self.segment_queue.put(("Interviewer", data), timeout=1)
                                except queue.Full:
                                    logger.warning("Segment queue full, dropping sys segment")
            except Exception as e:
                logger.error(f"Error in VAD worker: {e}", exc_info=True)
        logger.info("VAD worker stopped.")

    def _stt_worker(self):
        logger.info("STT worker started.")
        while self._pipeline_running:
            try:
                speaker, segment = self.segment_queue.get(timeout=0.1)
                t0 = time.time()
                
                if hasattr(self, 'on_mic_status_callback') and self.on_mic_status_callback:
                    self.on_mic_status_callback("PROCESSING")
                if hasattr(self, 'on_processing_state_callback') and self.on_processing_state_callback:
                    self.on_processing_state_callback("TRANSCRIBING")
                    
                logger.info(f"[stt] Transcribing {speaker}...")
                try:
                    prompt = self.config.stt_context_prompt
                    if self.config.ai_tone == "Conversational (Hinglish)":
                        prompt += " This is a bilingual interview. Apne bare mein batao, hum system design aur coding discuss karenge. Namaste."
                        
                    result = self.stt.transcribe(
                        segment, 
                        sample_rate=self.config.audio_sample_rate,
                        initial_prompt=prompt
                    )
                    stt_ms = (time.time() - t0) * 1000
                    logger.info(f"[stt] Transcript received ({len(result.text)} chars, {stt_ms:.1f}ms)")
                    if result.text:
                        tagged_text = f"[{speaker}]: {result.text}"
                        if hasattr(self, 'on_user_input_callback') and self.on_user_input_callback:
                            self.on_user_input_callback(tagged_text)
                        if hasattr(self, 'on_processing_state_callback') and self.on_processing_state_callback:
                            self.on_processing_state_callback("Analyzing intent...")
                            
                        self.session_manager.add_user_turn(result.text)
                        
                        intent_res = self.intent_detector.detect(result.text)
                        logger.info(f"[intent] {intent_res.intent.value}")
                        
                        # Phase 8 Command handling
                        if intent_res.intent.value == "COMMAND":
                            clear_phrases = ["reset session", "clear session", "clear conversation", "clear memory", "clear chat", "wipe memory", "forget everything", "new session", "fresh start"]
                            if any(p in intent_res.normalized_text for p in clear_phrases):
                                self.session_manager.reset_session()
                                # Full Privacy Wipe
                                self._last_screen_hash = None
                                self._last_ocr_res = None
                                self._last_analysis_res = None
                                self._last_coding_res = None
                                self.mm_engine.clear_context()
                                logger.info("[router] Route: LOCAL (Session Cleared)")
                                
                                if hasattr(self, 'on_clear_callback') and self.on_clear_callback:
                                    self.on_clear_callback()
                                if hasattr(self, 'on_processing_state_callback') and self.on_processing_state_callback:
                                    self.on_processing_state_callback("")
                                if hasattr(self, 'on_answer_callback') and self.on_answer_callback:
                                    self.on_answer_callback("Session cleared. Memory wiped.")
                            elif any(word in intent_res.normalized_text for word in ["exit", "quit", "close voro", "close application", "shut down"]):
                                logger.info("[router] Route: LOCAL (Exit Command Executed)")
                                if hasattr(self, 'on_answer_callback') and self.on_answer_callback:
                                    self.on_answer_callback("Goodbye!")
                                
                                if hasattr(self, 'on_quit_callback') and self.on_quit_callback:
                                    # Use a short timer so the UI has time to render "Goodbye!" before closing
                                    threading.Timer(1.0, self.on_quit_callback).start()
                                else:
                                    self.shutdown()
                        else:
                            # Route to AI
                            logger.info("[router] Route: AI")
                            req = PipelineRequest(
                                text=result.text,
                                intent=intent_res.intent.value
                            )
                            req.trace.stt_ms = stt_ms
                            self.latest_request_id = req.request_id
                            
                            # Backpressure: clear old pending items if AI is falling behind
                            while not self.ai_queue.empty():
                                try:
                                    self.ai_queue.get_nowait()
                                except queue.Empty:
                                    break
                                    
                            try:
                                self.ai_queue.put(req, timeout=1)
                            except queue.Full:
                                logger.warning("AI queue full, dropping intent")
                except Exception as e:
                    logger.error(f"Error during STT inference: {e}", exc_info=True)
                
                if hasattr(self, 'on_mic_status_callback') and self.on_mic_status_callback:
                    self.on_mic_status_callback("READY")
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error in STT worker: {e}", exc_info=True)
        logger.info("STT worker stopped.")

    def _ai_worker(self):
        logger.info("AI worker started.")
        import hashlib
        
        while self._pipeline_running:
            try:
                req: PipelineRequest = self.ai_queue.get(timeout=0.1)
                
                # Request cancellation
                if req.request_id != self.latest_request_id:
                    logger.info(f"Skipping obsolete request {req.request_id}")
                    continue
                    
                context = self.session_manager.get_context()
                
                try:
                    t_route = time.time()
                    reqs = self.intelligence_router.route(req.intent, req.text, context)
                    req.trace.routing_ms = (time.time() - t_route) * 1000
                    
                    if reqs.screen and getattr(self.config, 'ui_vision_enabled', True):
                        logger.info(f"[{req.request_id}] Screen context requested")
                        if hasattr(self, 'on_privacy_status_callback') and self.on_privacy_status_callback:
                            self.on_privacy_status_callback("CAPTURING SCREEN")
                        if hasattr(self, 'on_processing_state_callback') and self.on_processing_state_callback:
                            self.on_processing_state_callback("Analyzing screen...")
                        
                        t_cap = time.time()
                        
                        if req.intent == "SCREEN_UPDATE" and self.mm_engine.latest_ocr:
                            # We already have the OCR/base64 from the snip or monitor callback
                            frame = None
                            ocr_res = self.mm_engine.latest_ocr
                            logger.info(f"[{req.request_id}] Using pre-captured screen snippet")
                        else:
                            frame = self.screen_capture.capture_full_screen()
                        
                        req.trace.capture_ms = (time.time() - t_cap) * 1000
                        
                        if frame:
                            # Simple optimization: hash the image to skip OCR if unchanged
                            img_hash = hashlib.md5(frame.image.tobytes()[::100]).hexdigest()
                            
                            if img_hash == self._last_screen_hash and self._last_ocr_res:
                                logger.info(f"[{req.request_id}] Screen unchanged, reusing OCR cache")
                                ocr_res = self._last_ocr_res
                                analysis_res = self._last_analysis_res
                                coding_res = self._last_coding_res
                            else:
                                t_ocr = time.time()
                                skip_ocr_flag = getattr(self.config, 'activation_mode', 'basic') == 'premium'
                                ocr_res = self.ocr_engine.extract_text(frame, skip_ocr=skip_ocr_flag)
                                req.trace.ocr_ms = (time.time() - t_ocr) * 1000
                                
                                t_ana = time.time()
                                analysis_res = self.screen_analyzer.analyze(ocr_res)
                                req.trace.analysis_ms = (time.time() - t_ana) * 1000
                                
                                t_code = time.time()
                                coding_res = self.coding_detector.extract_context(analysis_res)
                                req.trace.analysis_ms += (time.time() - t_code) * 1000
                                
                                # Update cache
                                self._last_screen_hash = img_hash
                                self._last_ocr_res = ocr_res
                                self._last_analysis_res = analysis_res
                                self._last_coding_res = coding_res
                                
                            self.mm_engine.update_screen_context(ocr_res, analysis_res, coding_res)
                        elif req.intent == "SCREEN_UPDATE" and self.mm_engine.latest_ocr:
                            # Run analysis on the pre-captured OCR snippet
                            t_ana = time.time()
                            analysis_res = self.screen_analyzer.analyze(ocr_res)
                            req.trace.analysis_ms = (time.time() - t_ana) * 1000
                            
                            t_code = time.time()
                            coding_res = self.coding_detector.extract_context(analysis_res)
                            req.trace.analysis_ms += (time.time() - t_code) * 1000
                            
                            self.mm_engine.update_screen_context(ocr_res, analysis_res, coding_res)
                    else:
                        logger.info(f"[{req.request_id}] Screen context NOT requested")
                        
                    if hasattr(self, 'on_processing_state_callback') and self.on_processing_state_callback:
                        self.on_processing_state_callback("Generating answer...")
                        
                    t_llm = time.time()
                    full_answer = ""
                    is_first = True
                    
                    tts_buffer = ""
                    for chunk in self.answer_engine.generate_answer_stream(req.intent, context):
                        if req.request_id != self.latest_request_id:
                            self.tts_worker.stop_and_clear()
                            if hasattr(self, 'on_tts_stop_callback') and self.on_tts_stop_callback:
                                self.on_tts_stop_callback()
                            break # Request was superseded
                            
                        full_answer += chunk
                        
                        if not getattr(self.config, 'ui_tts_muted', False):
                            tts_buffer += chunk
                            # Split on boundaries
                            import re
                            if re.search(r'[.\?!\n:]+', tts_buffer):
                                self.tts_worker.enqueue(tts_buffer)
                                tts_buffer = ""
                        
                        if hasattr(self, 'on_answer_chunk_callback') and self.on_answer_chunk_callback:
                            self.on_answer_chunk_callback(chunk, is_first, False)
                        is_first = False
                        
                    if tts_buffer and req.request_id == self.latest_request_id and not getattr(self.config, 'ui_tts_muted', False):
                        self.tts_worker.enqueue(tts_buffer)

                    
                    req.trace.llm_ms = (time.time() - t_llm) * 1000
                    
                    # Ensure we are still the latest request before bubbling up to UI
                    if req.request_id == self.latest_request_id:
                        logger.info(f"[ai] Answer generated completely ({len(full_answer)} chars)")
                        t_ui = time.time()
                        if hasattr(self, 'on_answer_chunk_callback') and self.on_answer_chunk_callback:
                            self.on_answer_chunk_callback("", False, True)
                            
                        if not full_answer.startswith("Error") and not full_answer.startswith(" [Error"):
                            self.session_manager.add_assistant_turn(full_answer)
                        else:
                            if hasattr(self, 'on_error_callback') and self.on_error_callback:
                                self.on_error_callback(full_answer)
                                
                        if hasattr(self, 'on_privacy_status_callback') and self.on_privacy_status_callback:
                            self.on_privacy_status_callback("IDLE")
                        if hasattr(self, 'on_processing_state_callback') and self.on_processing_state_callback:
                            self.on_processing_state_callback("IDLE")
                            
                        req.trace.overlay_ms = (time.time() - t_ui) * 1000
                        
                        logger.info(f"[{req.request_id}] Pipeline Trace:\n"
                                    f"STT: {req.trace.stt_ms:.1f}ms | "
                                    f"Route: {req.trace.routing_ms:.1f}ms | "
                                    f"Cap: {req.trace.capture_ms:.1f}ms | "
                                    f"OCR: {req.trace.ocr_ms:.1f}ms | "
                                    f"Ana: {req.trace.analysis_ms:.1f}ms | "
                                    f"LLM: {req.trace.llm_ms:.1f}ms | "
                                    f"UI: {req.trace.overlay_ms:.1f}ms | "
                                    f"Total: {req.trace.total_ms:.1f}ms")
                    else:
                        logger.info(f"Discarded answer for {req.request_id} (superseded)")
                        
                except Exception as e:
                    logger.error(f"[{req.request_id}] Error during AI inference: {e}", exc_info=True)
                    if hasattr(self, 'on_error_callback') and self.on_error_callback:
                        self.on_error_callback("I encountered an internal error processing that request.")
                    if hasattr(self, 'on_processing_state_callback') and self.on_processing_state_callback:
                        self.on_processing_state_callback("IDLE")
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error in AI worker: {e}", exc_info=True)
        logger.info("AI worker stopped.")

    def run(self):
        """Main run loop to keep the application alive."""
        self.initialize()
        self.start()
        
        try:
            while self.state == ApplicationState.RUNNING:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
        finally:
            self.shutdown()

    def shutdown(self):
        """Cleanly shutdown the application."""
        if self.state in (ApplicationState.STOPPED, ApplicationState.STOPPING):
            return
            
        logger.info("Stopping Voro...")
        self.state = ApplicationState.STOPPING
        
        self._pipeline_running = False
        if self.ai_thread:
            logger.info("Stopping AI worker...")
            self.ai_thread.join(timeout=2)
        if self.stt_thread:
            logger.info("Stopping STT worker...")
            self.stt_thread.join(timeout=2)
        if self.vad_thread:
            logger.info("Stopping VAD worker...")
            self.vad_thread.join(timeout=2)
        
        try:
            if self.audio_capture:
                logger.info("Stopping audio capture...")
                self.audio_capture.stop()
                self.audio_capture.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down audio subsystem: {e}")
            
        self.state = ApplicationState.STOPPED
        logger.info("Voro stopped cleanly")


    def cycle_activation_mode(self):
        modes = ['premium', 'basic', 'local']
        current = getattr(self.config, 'activation_mode', 'basic')
        try:
            idx = modes.index(current)
        except ValueError:
            idx = 1
            
        next_mode = modes[(idx + 1) % len(modes)]
        self.config.activation_mode = next_mode
        
        import os
        from dotenv import set_key
        env_path = os.path.join(os.getcwd(), ".env")
        set_key(env_path, "ACTIVATION_MODE", next_mode)
        
        self.reload_ai_provider()
        
        # Trigger UI update if callback exists
        if hasattr(self, 'on_activation_switched_callback') and self.on_activation_switched_callback:
            self.on_activation_switched_callback(next_mode)

    def reload_ai_provider(self):
        logger.info("AI Provider initializing (NORVI AGENT MODE)...")
        from app.ai.openrouter import OpenRouterProvider
        
        # Hardcoded to Ollama with gemma4:cloud for Agency
        OLLAMA_MODEL = "gemma4:cloud"
        
        self.ai_provider = OpenRouterProvider(
            api_key="ollama_local",
            model=OLLAMA_MODEL,
            base_url="http://localhost:11434/v1"
        )
        ai_coding_provider = self.ai_provider
        ai_vision_provider = None # Text-only fallback for vision via OCR
        
        from app.answer.engine import AnswerEngine
        self.answer_engine = AnswerEngine(
            ai_provider=self.ai_provider,
            context_manager=self.context_manager,
            mm_engine=self.mm_engine,
            max_context_turns=self.config.conversation_history_depth * 2,
            ai_coding_provider=ai_coding_provider,
            ai_vision_provider=ai_vision_provider
        )
        return
        
        mode = getattr(self.config, 'activation_mode', 'basic')
        
        # Backwards compatibility check
        if getattr(self.config, 'use_ollama', False) and mode == 'basic':
            mode = 'local'
            
        from app.ai.openrouter import OpenRouterProvider
        
        if getattr(self.config, 'developer_mode', False):
            import os
            omni_key = getattr(self.config, 'omni_route_api_key', '') or os.environ.get("OMNIROUTER_API_KEY", "") or os.environ.get("OMNI_ROUTE_API_KEY", "")
            omni_model = getattr(self.config, 'omni_route_model', '') or os.environ.get("OMNIROUTER_MODEL", "") or os.environ.get("OMNI_ROUTE_MODEL", "") or "developer/model"
            logger.info(f"Using Developer Mode (Omni Route Proxy) with model: {omni_model}")
            self.ai_provider = OpenRouterProvider(
                api_key=omni_key,
                model=omni_model,
                base_url="http://localhost:20128/v1"
            )
            ai_coding_provider = self.ai_provider
            ai_vision_provider = self.ai_provider
        elif mode == 'premium':
            provider = getattr(self.config, 'premium_provider', 'OpenAI')
            logger.info(f"Using Premium AI Provider ({provider}) with model: {self.config.premium_model}")
            if "Anthropic" in provider:
                from app.ai.anthropic_provider import AnthropicProvider
                self.ai_provider = AnthropicProvider(
                    api_key=self.config.premium_api_key,
                    model=self.config.premium_model,
                    base_url="https://api.anthropic.com/v1/messages"
                )
            elif "Google" in provider:
                self.ai_provider = OpenRouterProvider(
                    api_key=self.config.premium_api_key,
                    model=self.config.premium_model,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
                )
            else:
                self.ai_provider = OpenRouterProvider(
                    api_key=self.config.premium_api_key,
                    model=self.config.premium_model,
                    base_url="https://api.openai.com/v1"
                )
            
            ai_coding_provider = self.ai_provider
            ai_vision_provider = self.ai_provider
            
        elif mode == 'local':
            logger.info(f"Using local Ollama chat model: {self.config.ollama_model}")
            self.ai_provider = OpenRouterProvider(
                api_key="ollama_local", # Dummy key
                model=self.config.ollama_model,
                base_url="http://localhost:11434/v1"
            )
            
            coding_model = getattr(self.config, 'ollama_coding_model', '') or self.config.ollama_model
            logger.info(f"Using local Ollama coding model: {coding_model}")
            ai_coding_provider = OpenRouterProvider(
                api_key="ollama_local",
                model=coding_model,
                base_url="http://localhost:11434/v1"
            )
            
            vision_model = getattr(self.config, 'ollama_vision_model', '')
            if vision_model:
                logger.info(f"Using local Ollama vision model: {vision_model}")
                ai_vision_provider = OpenRouterProvider(
                    api_key="ollama_local",
                    model=vision_model,
                    base_url="http://localhost:11434/v1"
                )
            else:
                logger.info("No vision model selected. Using OCR text-only mode.")
                ai_vision_provider = None
                
        else: # basic
            logger.info(f"Using Basic OpenRouter provider with model: {self.config.openrouter_model}")
            self.ai_provider = OpenRouterProvider(
                api_key=self.config.openrouter_api_key,
                model=self.config.openrouter_model,
                base_url=self.config.openrouter_base_url
            )
            ai_coding_provider = self.ai_provider
            ai_vision_provider = self.ai_provider
            
        from app.answer.engine import AnswerEngine
        self.answer_engine = AnswerEngine(
            ai_provider=self.ai_provider,
            context_manager=self.context_manager,
            mm_engine=self.mm_engine,
            max_context_turns=self.config.conversation_history_depth * 2,
            ai_coding_provider=ai_coding_provider,
            ai_vision_provider=ai_vision_provider
        )
