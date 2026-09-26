# Development Rules

## General
- Write clean, type-hinted Python code.
- Avoid massive, monolithic files; keep logic separated by domain (audio, UI, AI).
- Do not modify unrelated files when implementing a specific feature.

## Before Coding
- Review the ARCHITECTURE.md to ensure proper placement of new logic.
- Verify that heavy operations (file I/O, network requests, model inference) are decoupled from the main thread.

## UI (PySide6)
- Always use the UIBridge (Qt Signals) to communicate between background workers and the PySide6 UI.
- Never directly modify UI elements from a background 	hreading.Thread.
- Respect DESIGN.md guidelines for styling and layouts.

## Audio Processing
- Ensure ultra-low latency. Keep VAD silence thresholds around 800ms.
- Limit MKL threads (cpu_threads=4) for aster-whisper to prevent memory allocation crashes on Windows.
- Clean up temporary audio files immediately after playback.

## Security
- Never hardcode API keys. Always use .env and Python's os.environ or dotenv.
- Never automatically download massive ML models without explicit user consent and visible progress indicators.