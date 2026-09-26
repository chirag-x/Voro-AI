# Voro AI Desktop Assistant

Voro is an ultra-low latency, multimodal, screen-aware AI desktop assistant. Designed to seamlessly integrate into your workflow, Voro sits as a transparent overlay on your screen, ready to see, hear, and help you without forcing you to switch contexts.

## Features
- **Screen Awareness**: Voro can "see" your screen using intelligent OCR and vision processing.
- **Conversational Speed**: Sub-second latency utilizing local aster-whisper and optimized edge-TTS.
- **Privacy First**: Fully supports offline LLM execution via Ollama. 
- **Screenshare Ghosting**: Custom hardware audio routing ensures Voro's voice is never captured by Discord or Google Meet screenshares.

## Installation

1. Clone the repository:
   `ash
   git clone https://github.com/chirag-x/Voro-AI.git
   cd Voro-AI
   `

2. Create a virtual environment and install dependencies:
   `ash
   python -m venv .venv
   .venv\Scriptsctivate
   pip install -r requirements.txt
   `

3. Setup your .env file by copying .env.example to .env and filling in your API keys.

4. Run the application:
   `ash
   python main.py
   `

## Usage
- Press the configured global hotkey (default: Ctrl+Shift+Space) to wake Voro.
- Speak naturally. Voro will detect when you stop speaking, process the input, and reply instantly.
- Access the Settings menu from the System Tray to download new voice models, change your output device, or adjust the AI's personality.

## License
Designed and Developed by Chirag Sharma.