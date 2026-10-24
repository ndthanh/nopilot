@echo off
setlocal
if defined COPILOT_PYTHON (
  "%COPILOT_PYTHON%" -B "%~dp0web_server.py" %*
) else if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -B "%~dp0web_server.py" %*
) else (
  python -B "%~dp0web_server.py" %*
)
exit /b %errorlevel%
