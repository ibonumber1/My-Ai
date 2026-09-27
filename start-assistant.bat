@echo off
rem Starts the voice assistant. Keep this window open; closing it stops the assistant.
cd /d "%~dp0"
.venv\Scripts\python -m uvicorn assistant.server:app --host 0.0.0.0 --port 8000
pause
