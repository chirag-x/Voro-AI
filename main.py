import sys
import os

# Universal fix for --noconsole crashing on print() or sys.stderr.write()
class DummyIO:
    def write(self, *args, **kwargs): pass
    def flush(self, *args, **kwargs): pass
    def isatty(self): return False

if sys.stdout is None:
    sys.stdout = DummyIO()
if sys.stderr is None:
    sys.stderr = DummyIO()

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from app.core.norvi_gatekeeper import require_license
from app.core.application import VoroApplication
from app.core.config import get_env_path
from app.ui.overlay import OverlayWindow, UIBridge
from app.utils.logging import logger
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="sounddevice")
warnings.filterwarnings("ignore", module="soundcard")
warnings.filterwarnings("ignore", message="data discontinuity in recording")

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def global_exception_handler(exc_type, exc_value, exc_traceback):
    from app.utils.logging import logger
    import sys
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Uncaught Exception:", exc_info=(exc_type, exc_value, exc_traceback))

def main():
    import sys
    sys.excepthook = global_exception_handler
    try:
        # Force Windows to group this separately from python.exe
        if sys.platform == "win32":
            import ctypes
            myappid = 'voro.assistant.app.1.0'
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass
                
        # Create Qt App
        qt_app = QApplication(sys.argv)
        
        # Start Ollama Manager
        try:
            from app.core.ollama_manager import manager as ollama_manager
            ollama_manager.check_and_start()
        except Exception as e:
            logger.error(f"Failed to initialize Ollama Manager: {e}")
            
        # --- NORVI ANTI-PIRACY GATEKEEPER ---
        from app.core.norvi_gatekeeper import require_license
        if not require_license("voro"):
            sys.exit(0)
        # ------------------------------------
        # Force a global normal mouse pointer (stealth mode)
        # This prevents the mouse turning into an "I" text cursor over invisible input fields
        from PySide6.QtCore import Qt
        qt_app.setOverrideCursor(Qt.ArrowCursor)
        
        # Set App Icon
        icon_path = resource_path("logo.png")
        if os.path.exists(icon_path):
            qt_app.setWindowIcon(QIcon(icon_path))
        
        # Enable Ctrl-C to kill the Qt app
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        
        # Create UI
        overlay = OverlayWindow()
        bridge = UIBridge()
        overlay.bridge = bridge  # Pass bridge reference to overlay so it can emit signals
        bridge.answer_received.connect(overlay.update_answer)
        bridge.answer_chunk_received.connect(overlay.update_answer_chunk)
        bridge.privacy_status_updated.connect(overlay.update_privacy_status)
        bridge.mic_status_updated.connect(overlay.update_mic_status)
        bridge.ai_status_updated.connect(overlay.update_ai_status)
        bridge.user_input_received.connect(overlay.update_user_input)
        bridge.processing_state_updated.connect(overlay.update_processing_state)
        bridge.error_received.connect(overlay.update_error)
        bridge.clear_session.connect(overlay.clear)
        bridge.quit_application.connect(qt_app.quit)
        bridge.activation_switched.connect(overlay.update_activation_label)
        bridge.tts_audio_ready.connect(overlay.play_tts_audio)
        bridge.tts_stop.connect(overlay.stop_tts_audio)
        bridge.config_updated.connect(overlay._update_indicators)

        bridge.toggle_visibility.connect(overlay.toggle_visibility)
        
        # Create Core Voro App
        voro_app = VoroApplication()
        bridge.model_switched.connect(voro_app.switch_model)
        bridge.profile_updated.connect(voro_app.reload_context)
        voro_app.on_answer_callback = bridge.answer_received.emit
        voro_app.on_answer_chunk_callback = bridge.answer_chunk_received.emit
        voro_app.on_privacy_status_callback = bridge.privacy_status_updated.emit
        voro_app.on_mic_status_callback = bridge.mic_status_updated.emit
        voro_app.on_ai_status_callback = bridge.ai_status_updated.emit
        voro_app.on_user_input_callback = bridge.user_input_received.emit
        voro_app.on_processing_state_callback = bridge.processing_state_updated.emit
        voro_app.on_error_callback = bridge.error_received.emit
        voro_app.on_clear_callback = bridge.clear_session.emit
        voro_app.on_quit_callback = bridge.quit_application.emit
        voro_app.on_activation_switched_callback = bridge.activation_switched.emit
        voro_app.on_tts_audio_callback = bridge.tts_audio_ready.emit
        voro_app.on_tts_stop_callback = bridge.tts_stop.emit
        
        # Show overlay first so user knows something is happening
        overlay.show()
        
        # Tray is now handled in overlay.py
        overlay._apply_taskbar_state()
        
        # Start initialization in a background thread so it doesn't block the Qt event loop
        import threading
        def startup_routine():
            try:
                voro_app.initialize()
                voro_app.start()
            except Exception as e:
                logger.error(f"Startup routine failed: {e}")
                bridge.error_received.emit(f"Failed to start: {e}")
                
        threading.Thread(target=startup_routine, daemon=True).start()
        
        # Snipping Overlay Initialization
        from app.ui.snipping import SnipOverlay
        from app.ai.ocr import extract_text_from_pixmap
        snip_overlay = SnipOverlay()
        
        def handle_snip_completed(pixmap):
            def process_ocr():
                bridge.processing_state_updated.emit("ANALYZING SCREEN...")
                try:
                    image = pixmap.toImage()
                    
                    from PySide6.QtCore import QByteArray, QBuffer, QIODevice
                    from PIL import Image
                    import io
                    
                    ba = QByteArray()
                    buffer = QBuffer(ba)
                    buffer.open(QIODevice.WriteOnly)
                    image.save(buffer, "PNG")
                    
                    pil_img = Image.open(io.BytesIO(ba.data())).convert('RGB')
                    
                    voro_app.on_snip_callback(pil_img, auto=True)
                    bridge.processing_state_updated.emit("")
                except Exception as e:
                    logger.error(f"Error converting snip to image: {e}")
                    bridge.processing_state_updated.emit("SCREEN CAPTURE FAILED")
            # Process in thread to avoid blocking Qt
            threading.Thread(target=process_ocr, daemon=True).start()
            
        snip_overlay.snip_completed.connect(handle_snip_completed)
        
        # Signals for triggering Snipping from background hotkey
        # We must call show() from main Qt thread, so we'll add a signal to UIBridge
        bridge.trigger_snip.connect(snip_overlay.showFullScreen)
        bridge.toggle_taskbar.connect(overlay.toggle_taskbar_visibility)
        bridge.toggle_tray.connect(overlay.toggle_tray_visibility)
        bridge.toggle_stealth.connect(overlay.toggle_stealth_mode)
        
        # Global Hotkeys
        try:
            import keyboard
            hotkey = voro_app.config.ui_global_hotkey
            keyboard.add_hotkey(hotkey, bridge.toggle_visibility.emit)
            logger.info(f"Global hotkey registered: {hotkey}")
            
            # Hint Mode Hotkey
            hint_hotkey = voro_app.config.ui_hint_hotkey
            def toggle_hint_mode():
                voro_app.config.hint_mode_active = not voro_app.config.hint_mode_active
                state = "ON" if voro_app.config.hint_mode_active else "OFF"
                bridge.processing_state_updated.emit(f"HINT MODE {state}")
            keyboard.add_hotkey(hint_hotkey, toggle_hint_mode)
            logger.info(f"Hint mode hotkey registered: {hint_hotkey}")
            
            # Snip Hotkey
            snip_hotkey = voro_app.config.ui_snip_hotkey
            keyboard.add_hotkey(snip_hotkey, bridge.trigger_snip.emit)
            logger.info(f"Snip mode hotkey registered: {snip_hotkey}")
            
            # Taskbar Toggle Hotkey
            taskbar_hotkey = getattr(voro_app.config, 'ui_taskbar_hotkey', 'ctrl+shift+t')
            keyboard.add_hotkey(taskbar_hotkey, bridge.toggle_taskbar.emit)
            logger.info(f"Taskbar toggle hotkey registered: {taskbar_hotkey}")
            
            # Mute Hotkeys
            def toggle_mute_mic(*args):
                logger.debug("Toggle mute mic triggered")
                voro_app.config.mute_user_mic = not voro_app.config.mute_user_mic
                state = "MUTED" if voro_app.config.mute_user_mic else "UNMUTED"
                bridge.processing_state_updated.emit(f"USER MIC {state}")
                import os
                from dotenv import set_key
                val = str(voro_app.config.mute_user_mic)
                os.environ["MUTE_USER_MIC"] = val
                set_key(get_env_path(), "MUTE_USER_MIC", val)
                bridge.config_updated.emit()
                
            def toggle_mute_sys(*args):
                voro_app.config.mute_system_audio = not voro_app.config.mute_system_audio
                state = "MUTED" if voro_app.config.mute_system_audio else "UNMUTED"
                bridge.processing_state_updated.emit(f"SYS AUDIO {state}")
                import os
                from dotenv import set_key
                val = str(voro_app.config.mute_system_audio)
                os.environ["MUTE_SYSTEM_AUDIO"] = val
                set_key(get_env_path(), "MUTE_SYSTEM_AUDIO", val)
                bridge.config_updated.emit()
                
            mic_hotkey = getattr(voro_app.config, 'ui_mute_mic_hotkey', 'ctrl+shift+m')
            sys_hotkey = getattr(voro_app.config, 'ui_mute_sys_hotkey', 'ctrl+shift+a')
            
            keyboard.add_hotkey(mic_hotkey, toggle_mute_mic)
            logger.info(f"Mute User Mic hotkey registered: {mic_hotkey}")
            
            keyboard.add_hotkey(sys_hotkey, toggle_mute_sys)
            logger.info(f"Mute System Audio hotkey registered: {sys_hotkey}")
            
            def toggle_mute_tts(*args):
                voro_app.config.ui_tts_muted = not getattr(voro_app.config, 'ui_tts_muted', False)
                state = "MUTED" if voro_app.config.ui_tts_muted else "UNMUTED"
                bridge.processing_state_updated.emit(f"VORO VOICE {state}")
                import os
                from dotenv import set_key
                val = str(voro_app.config.ui_tts_muted)
                os.environ["UI_TTS_MUTED"] = val
                set_key(get_env_path(), "UI_TTS_MUTED", val)
                bridge.config_updated.emit()
                if voro_app.config.ui_tts_muted:
                    bridge.tts_stop.emit()
            
            tts_hotkey = getattr(voro_app.config, 'ui_tts_mute_hotkey', 'ctrl+shift+x')
            keyboard.add_hotkey(tts_hotkey, toggle_mute_tts)
            logger.info(f"Mute Voro Voice hotkey registered: {tts_hotkey}")

            # Connect overlay toggle clicks
            overlay.user_mic_toggled.connect(toggle_mute_mic)
            overlay.sys_mic_toggled.connect(toggle_mute_sys)
            overlay.tts_toggled.connect(toggle_mute_tts)
            
            # Cycle Mode Hotkey
            cycle_hotkey = getattr(voro_app.config, 'ui_cycle_mode_hotkey', 'ctrl+shift+v')
            keyboard.add_hotkey(cycle_hotkey, voro_app.cycle_activation_mode)
            logger.info(f"Cycle Mode hotkey registered: {cycle_hotkey}")
            
            # Quick Prompts Hotkeys
            def make_quick_prompt_handler(prompt_text):
                def handler():
                    logger.info(f"Triggering Quick Prompt: {prompt_text}")
                    voro_app.inject_user_input(prompt_text)
                return handler

            for i in range(1, 4):
                hk = getattr(voro_app.config, f'ui_quick_prompt_{i}_hotkey', '')
                txt = getattr(voro_app.config, f'ui_quick_prompt_{i}_text', '')
                if hk and txt:
                    keyboard.add_hotkey(hk, make_quick_prompt_handler(txt))
                    logger.info(f"Quick Prompt {i} hotkey registered: {hk}")
                    
            stop_hk = getattr(voro_app.config, 'ui_stop_hotkey', 'ctrl+shift+c')
            keyboard.add_hotkey(stop_hk, voro_app.stop_current_task)
            logger.info(f"Stop Task hotkey registered: {stop_hk}")

            clear_hk = getattr(voro_app.config, 'ui_clear_session_hotkey', 'ctrl+shift+backspace')
            keyboard.add_hotkey(clear_hk, bridge.clear_session.emit)
            logger.info(f"Clear Session hotkey registered: {clear_hk}")

            tray_hk = getattr(voro_app.config, 'ui_toggle_tray_hotkey', 'ctrl+shift+y')
            keyboard.add_hotkey(tray_hk, bridge.toggle_tray.emit)
            logger.info(f"Toggle Tray hotkey registered: {tray_hk}")

            stealth_hk = getattr(voro_app.config, 'ui_stealth_hotkey', 'ctrl+shift+g')
            keyboard.add_hotkey(stealth_hk, bridge.toggle_stealth.emit)
            logger.info(f"Stealth Mode hotkey registered: {stealth_hk}")
            
            
        except Exception as e:
            logger.error(f"Failed to register global hotkeys: {e}")
            
        # Run Qt Event Loop (blocks here until window closed or app quit)
        exit_code = qt_app.exec()
        
        # Shutdown core gracefully
        try:
            from app.core.ollama_manager import manager as ollama_manager
            ollama_manager.shutdown()
        except Exception:
            pass
        voro_app.shutdown()
        sys.exit(exit_code)
        
    except Exception as e:
        logger.critical(f"Critical failure: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

