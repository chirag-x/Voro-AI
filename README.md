# Voro
## Overview
Voro is a standalone desktop application built entirely in Python, utilizing PySide6 for the graphical user interface. It operates using a modular architecture separating the GUI, audio processing pipelines, AI reasoning, and screen capture mechanisms.

Voro is a cutting-edge, stealthy local AI assistant explicitly designed to help you ace your technical and behavioral interviews. Taking inspiration from tools like Parakeet.ai and Chiku.ai, Voro acts as an invisible pair-programmer and co-pilot during live video interviews.

By securely capturing your screen (via local OCR) and listening to your system audio (interviewer) + microphone (you) in real-time, Voro seamlessly generates the exact answers you should say out loud, projecting them onto a translucent, screen-share-proof overlay.

### Key Features
- **Total Stealth**: Built with WDA_EXCLUDEFROMCAPTURE, Voro\'s interface is completely invisible to screen-sharing software (Zoom, Teams, Meet). Even the Snipping Tool cursor is forced to look like a normal mouse pointer.
- **Multi-Tier AI Activation**:
  - **Premium Mode**: Directly hooks into top-tier vision models (GPT-4o, Claude 3.5 Sonnet) to natively read your screen.
  - **Local Mode**: Uses 100% free, offline, local Ollama models with EasyOCR.
  - **Basic Mode**: Uses free OpenRouter models with local OCR fallback.
- **Context-Aware Memory**: Remembers your resume, past projects, and the context of the interview.
- **Automated Coding Intelligence**: Can instantly detect Python, JavaScript, Java, and C++ on your screen and act as a senior developer helping you debug it live.

# Voro AI Desktop Assistant

Voro is an ultra-low latency, multimodal, screen-aware AI desktop assistant. Designed to seamlessly integrate into your workflow, Voro sits as a transparent overlay on your screen, ready to see, hear, and help you without forcing you to switch contexts.

## Features
- **Screen Awareness**: Voro can "see" your screen using intelligent OCR and vision processing.
- **Conversational Speed**: Sub-second latency utilizing local aster-whisper and optimized edge-TTS.
- **Privacy First**: Fully supports offline LLM execution via Ollama. 
- **Screenshare Ghosting**: Custom hardware audio routing ensures Voro's voice is never captured by Discord or Google Meet screenshares.

## Usage
- Press the configured global hotkey (default: Ctrl+Shift+Space) to wake Voro.
- Speak naturally. Voro will detect when you stop speaking, process the input, and reply instantly.
- Access the Settings menu from the System Tray to download new voice models, change your output device, or adjust the AI's personality.

## License
Designed and Developed by Chirag Sharma.