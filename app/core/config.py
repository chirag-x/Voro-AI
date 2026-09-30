import os
from pydantic import Field
from pydantic_settings import BaseSettings
from app.utils.errors import ConfigError

class VoroConfig(BaseSettings):
    """
    Configuration for the Voro application.
    Loaded from environment variables or .env file.
    """
    first_run_completed: bool = Field(default=False)
    # Activation Mode
    activation_mode: str = Field(default="basic") # "premium", "basic", "local"
    developer_mode: bool = Field(default=False, env="DEVELOPER_MODE")
    
    # Premium AI (Paid API)
    premium_provider: str = Field(default="OpenAI")
    premium_api_key: str = Field(default="")
    premium_model: str = Field(default="gpt-4o")
    omni_route_api_key: str = Field(default="", env="OMNI_ROUTE_API_KEY")
    omni_route_model: str = Field(default="", env="OMNI_ROUTE_MODEL")
    
    # OCR Customization
    tesseract_path: str = Field(default=r"C:\Program Files\Tesseract-OCR\tesseract.exe")

    # OpenRouter (Basic)
    openrouter_api_key: str = Field(default="")
    openrouter_model: str = Field(default="google/gemini-2.5-flash-lite-preview-02-05:free")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")

    # Audio Settings
    audio_sample_rate: int = Field(default=16000)
    audio_channels: int = Field(default=1)
    audio_chunk_size: int = Field(default=1024)

    ui_opacity: int = Field(default=100) # Master Opacity
    ui_bg_opacity: int = Field(default=100, env="UI_BG_OPACITY") # Background Base Opacity
    ui_text_opacity: int = Field(default=100, env="UI_TEXT_OPACITY") # Text Base Opacity
    ui_you_heading_color: str = Field(default="#E53935")       # YOU heading
    ui_interviewer_heading_color: str = Field(default="#FF9900") # INTERVIEWER heading
    ui_voro_heading_color: str = Field(default="#0055A4")      # VORO heading
    ui_font_size: int = Field(default=13)
    ui_win_x: int = Field(default=-1)
    ui_win_y: int = Field(default=-1)
    ui_win_w: int = Field(default=400)
    ui_win_h: int = Field(default=400)
    
    ui_settings_win_x: int = Field(default=-1)
    ui_settings_win_y: int = Field(default=-1)
    ui_settings_win_w: int = Field(default=900)
    ui_settings_win_h: int = Field(default=650)
    ui_show_in_taskbar: bool = Field(default=False)
    ui_show_tray: bool = Field(default=True)
    ui_always_on_top: bool = Field(default=False, env="UI_ALWAYS_ON_TOP")
    ui_theme_mode: str = Field(default="system")
    ui_remember_position: bool = Field(default=True, env="UI_REMEMBER_POSITION")
    mute_user_mic: bool = Field(default=False, env="MUTE_USER_MIC")
    mute_system_audio: bool = Field(default=False, env="MUTE_SYSTEM_AUDIO")
    user_audio_device: str = Field(default="Default Windows Input", env="USER_AUDIO_DEVICE")
    system_audio_device: str = Field(default="Default Windows Output", env="SYSTEM_AUDIO_DEVICE")
    ui_tts_volume: int = Field(default=100, env="UI_TTS_VOLUME")

    ui_global_hotkey: str = Field(default="ctrl+space", env="UI_GLOBAL_HOTKEY")
    ui_hint_hotkey: str = Field(default="ctrl+shift+h", env="UI_HINT_HOTKEY")
    ui_snip_hotkey: str = Field(default="ctrl+shift+p", env="UI_SNIP_HOTKEY")
    ui_stealth_hotkey: str = Field(default="ctrl+shift+g", env="UI_STEALTH_HOTKEY")
    ui_taskbar_hotkey: str = Field(default="ctrl+shift+t", env="UI_TASKBAR_HOTKEY")
    ui_clear_session_hotkey: str = Field(default="ctrl+shift+backspace", env="UI_CLEAR_SESSION_HOTKEY")
    ui_toggle_tray_hotkey: str = Field(default="ctrl+shift+y", env="UI_TOGGLE_TRAY_HOTKEY")
    ui_mute_mic_hotkey: str = Field(default="ctrl+shift+m", env="UI_MUTE_MIC_HOTKEY")
    ui_mute_sys_hotkey: str = Field(default="ctrl+shift+a", env="UI_MUTE_SYS_HOTKEY")
    ui_cycle_mode_hotkey: str = Field(default="ctrl+shift+v", env="UI_CYCLE_MODE_HOTKEY")
    ui_maximize_hotkey: str = Field(default="F11", env="UI_MAXIMIZE_HOTKEY")
    ui_tts_mute_hotkey: str = Field(default="ctrl+shift+x", env="UI_TTS_MUTE_HOTKEY")
    ui_tts_muted: bool = Field(default=False, env="UI_TTS_MUTED")
    ui_quick_prompt_1_hotkey: str = Field(default="ctrl+shift+1", env="UI_QUICK_PROMPT_1_HOTKEY")
    ui_quick_prompt_1_text: str = Field(default="Give me the correct answer for the question currently on the screen.", env="UI_QUICK_PROMPT_1_TEXT")
    ui_quick_prompt_2_hotkey: str = Field(default="ctrl+shift+2", env="UI_QUICK_PROMPT_2_HOTKEY")
    ui_quick_prompt_2_text: str = Field(default="Explain the code on my screen.", env="UI_QUICK_PROMPT_2_TEXT")
    ui_quick_prompt_3_hotkey: str = Field(default="ctrl+shift+3", env="UI_QUICK_PROMPT_3_HOTKEY")
    ui_quick_prompt_3_text: str = Field(default="Summarize the text on my screen.", env="UI_QUICK_PROMPT_3_TEXT")
    ui_voice: str = Field(default="en-US-AriaNeural", env="UI_VOICE")
    ui_capture_mode: str = Field(default="monitor", env="UI_CAPTURE_MODE")
    ui_capture_target: str = Field(default="1", env="UI_CAPTURE_TARGET")
    ui_auto_update: bool = Field(default=True, env="UI_AUTO_UPDATE")
    ui_stop_hotkey: str = Field(default="ctrl+shift+c", env="UI_STOP_HOTKEY")
    ui_vision_enabled: bool = Field(default=True, env="UI_VISION_ENABLED")
    ui_tts_rate: str = Field(default="+0%", env="UI_TTS_RATE")
    ui_tts_output_device: str = Field(default="Default System Device", env="UI_TTS_OUTPUT_DEVICE")
    hint_mode_active: bool = Field(default=False)  # Runtime only

    # AI Options
    use_ollama: bool = Field(default=False, env="USE_OLLAMA")
    ollama_model: str = Field(default="qwen2.5:7b", env="OLLAMA_MODEL")
    ollama_coding_model: str = Field(default="", env="OLLAMA_CODING_MODEL")
    ollama_vision_model: str = Field(default="", env="OLLAMA_VISION_MODEL")
    ai_tone: str = Field(default="Conversational (Script)", env="AI_TONE")
    stt_model_size: str = Field(default="tiny.en", env="STT_MODEL_SIZE")
    stt_device: str = Field(default="cpu", env="STT_DEVICE")
    stt_model_dir: str = Field(default="", env="STT_MODEL_DIR")
    groq_api_key: str = Field(default="", env="GROQ_API_KEY")
    stt_context_prompt: str = Field(default="This is a highly technical software engineering interview covering programming, system design, and coding.", env="STT_CONTEXT_PROMPT")
    enable_web_search: bool = Field(default=False, env="ENABLE_WEB_SEARCH")
    enable_auto_monitor: bool = Field(default=False, env="ENABLE_AUTO_MONITOR")

    # Additional model slots (slot 1 = openrouter_model, slots 2-5 optional)
    openrouter_model_2: str = Field(default="")
    openrouter_model_3: str = Field(default="")
    openrouter_model_4: str = Field(default="")
    openrouter_model_5: str = Field(default="")

    ocr_device: str = Field(default="gpu")

    # Conversation history: number of past Q&A exchanges sent to AI (1 exchange = 1 user + 1 assistant turn)
    conversation_history_depth: int = Field(default=6)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

def load_config() -> VoroConfig:
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
        return VoroConfig()
    except Exception as e:
        raise ConfigError(f"Failed to load configuration: {e}")
