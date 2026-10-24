@echo off
setlocal
python -m venv "%~dp0.venv"
if errorlevel 1 exit /b 1
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
exit /b %errorlevel%
