# Project Memory

## Current Status
- Core conversational loop (VAD -> STT -> LLM -> TTS) is fully functional.
- Settings UI is completed and synced with the .env file.
- Hardware audio routing and PySide6 audio chunk sequencing are stable.
- MKL memory allocation bugs in PyInstaller builds have been resolved.

## Completed
- PySide6 overlay setup.
- Whisper model downloading logic with custom progress bar tracking.
- Audio streaming pipeline with ultra-low latency configurations (800ms VAD).

## Current Task
- General maintenance, code cleanup, and preparation for deployment/packaging.

## Known Issues
- OCR accuracy can vary depending on screen resolution and scaling.
- Heavy local LLMs (Ollama) may consume significant RAM alongside Whisper models.

## Next Step
- Finalize documentation.
- Implement automated testing for the audio pipeline.