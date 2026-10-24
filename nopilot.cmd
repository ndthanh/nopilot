@echo off
setlocal
if defined COPILOT_PYTHON (
  "%COPILOT_PYTHON%" -B "%~dp0cli.py" %*
) else if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -B "%~dp0cli.py" %*
) else (
  python -B "%~dp0cli.py" %*
)
exit /b %errorlevel%
