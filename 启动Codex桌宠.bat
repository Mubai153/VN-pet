@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "%~dp0codex_desktop_pet.py"
    exit /b
)
pythonw codex_desktop_pet.py
