@echo off
setlocal
where uv >nul 2>nul
if %errorlevel% equ 0 (
  uv run --no-project --system-certs --with-requirements "%~dp0requirements-flash.txt" python "%~dp0flash.py" %*
  exit /b
)
py -3 -m venv "%~dp0..\.flash-venv"
if errorlevel 1 exit /b 1
"%~dp0..\.flash-venv\Scripts\python.exe" -m pip install -r "%~dp0requirements-flash.txt"
if errorlevel 1 exit /b 1
"%~dp0..\.flash-venv\Scripts\python.exe" "%~dp0flash.py" %*
exit /b %errorlevel%
