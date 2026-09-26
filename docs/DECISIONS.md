# Architecture Decisions

## ADR-001
**Decision**: Use PySide6 instead of Tkinter or PyQt5.
**Reason**: PySide6 provides modern, hardware-accelerated GUI rendering, native Windows system tray support, and is the official Python binding for Qt, ensuring long-term support and excellent frameless window capabilities.

## ADR-002
**Decision**: Use aster-whisper instead of standard whisper or cloud APIs.
**Reason**: Privacy and latency. aster-whisper runs locally using CTranslate2, offering significantly faster transcription speeds than the original OpenAI implementation, which is critical for real-time conversational latency.

## ADR-003
**Decision**: Implement a dynamic hardware audio routing engine instead of standard default playback.
**Reason**: To prevent standard Windows screenshare tools (Discord, Teams, Meet) from capturing Voro's voice. By explicitly selecting a Virtual Audio Cable or specific headphone pin, we bypass the Windows Media Foundation default capture hooks.