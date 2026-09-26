# Product Requirements Document

## Product
Voro AI Desktop Assistant

## Problem
Professionals and developers experience workflow disruption due to constant context-switching when using web-based AI tools. Standard voice assistants lack screen awareness, depend on high-latency cloud processing, and suffer from privacy issues where their voice is captured during screen-sharing sessions (e.g., Discord, Google Meet).

## Target Users
Developers, professionals, students, and power users who need instant, context-aware AI assistance without leaving their current application.

## Goal
Create a native, ultra-low latency desktop overlay assistant that provides screen-aware, conversational AI capabilities with strict privacy and offline support.

## Core Features
1. Transparent, always-on-top desktop overlay (PySide6).
2. Ultra-low latency Speech-to-Text (STT) via local aster-whisper.
3. Screen-awareness via Optical Character Recognition (OCR) and multimodal vision.
4. Seamless integration with local LLMs (Ollama) and cloud LLMs (OpenRouter).
5. Isolated hardware-routed Text-to-Speech (TTS) to bypass screenshare hooks.
6. Customizable AI tones and prompt management.

## MVP
- Global hotkey activation.
- Local STT transcription.
- LLM text generation.
- TTS voice playback.
- Basic screen snipping for OCR.

## Out of Scope
- Mobile companion app.
- Multi-user collaborative workspaces.
- Cloud-synced conversation history.

## Success Criteria
- User can trigger the assistant with a hotkey.
- Assistant can accurately read screen contents.
- Latency between speech end and AI response start is < 800ms.
- AI voice output is NOT captured by standard screensharing software.