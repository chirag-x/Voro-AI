# Architecture

## Overview
Voro is a standalone desktop application built entirely in Python, utilizing PySide6 for the graphical user interface. It operates using a modular architecture separating the GUI, audio processing pipelines, AI reasoning, and screen capture mechanisms.

## Tech Stack
- **Language**: Python 3.10+
- **Frontend / GUI**: PySide6 (Qt for Python)
- **STT (Speech-to-Text)**: faster-whisper (Offline, CTranslate2 engine)
- **TTS (Text-to-Speech)**: edge-tts, sounddevice, PyAV, PyAudio
- **LLM Engine**: Ollama (Local execution), OpenRouter (Cloud execution)
- **Vision / OCR**: PyAutoGUI, pytesseract / Windows Native OCR
- **Environment**: .env for configuration management.

## Architecture Flow
User Speech -> VAD (Voice Activity Detection) -> STT (Faster-Whisper) -> Text Prompt -> Answer Engine (LLM) -> Text Stream -> TTS Worker (Edge-TTS) -> PySide6 QMediaPlayer / SoundDevice -> Hardware Audio Output.

## Folder Structure
`
voro/
├── app/
│   ├── ai/          # Vision and OCR processing
│   ├── answer/      # LLM generation and API routing
│   ├── audio/       # VAD, TTS, and custom audio routing
│   ├── core/        # Application lifecycle and config
│   ├── screen/      # Screen snipping and capture
│   ├── speech/      # STT models (Faster-whisper)
│   └── ui/          # PySide6 Windows, Overlays, and Settings
├── docs/            # Project documentation
├── temp_tts/        # Temporary audio chunk storage
├── .env             # User configurations
└── main.py          # Application entry point
`

## Architectural Rules
- UI components must never block the main Qt Event Loop.
- Audio and LLM generation must occur in background daemon threads (QThread or 	hreading.Thread).
- Thread communication to the UI must use Qt Signals (UIBridge).
- The application must gracefully fallback to CPU processing if CUDA/GPU is unavailable.