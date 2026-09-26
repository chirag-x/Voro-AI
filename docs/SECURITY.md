# Security Requirements

## API Keys
- Never expose OpenRouter or other API keys in the source code.
- Keys must be stored locally in the .env file within the user's secure AppData or Installation directory.

## Privacy
- Voro must only capture screen contents when explicitly triggered by the user.
- Microphone listening must only occur when the hotkey is activated or during a deliberate conversational turn.
- Audio and screen data must be processed locally whenever possible.
- No telemetry or usage data should be silently collected.

## File I/O
- Temporary TTS audio files must be securely deleted from the system immediately after playback to prevent storage bloat and data recovery.
- Downloaded STT models must be verified to prevent executing arbitrary malicious tensors.