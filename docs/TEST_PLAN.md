# Test Plan

## Core Interaction
- User can trigger Voro using the designated global hotkey.
- Voro accurately transcribes spoken English and Hinglish phrases.
- Voro generates a contextual response via the selected LLM.
- Voro plays the generated response audibly without skipping chunks.

## Settings & Configuration
- Changing the AI Tone in Settings immediately reflects in the next conversation.
- Downloading a new STT model saves it to the custom selected directory.
- Changing the Output Audio Device successfully routes the TTS audio to that specific hardware endpoint.

## Performance & Latency
- The delay between the user stopping speech and the TTS starting should be < 1.5 seconds on average hardware.
- Memory usage must remain stable over extended sessions (no memory leaks in temporary audio chunk generation).

## Edge Cases
- Disconnecting the internet cleanly falls back to local models or reports an error without crashing.
- PyInstaller --noconsole executable boots without NoneType sys.stdout/sys.stderr exceptions.