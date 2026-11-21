@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (set "PYTHON=python") else (set "PYTHON=py -3")
%PYTHON% -m PyInstaller --noconfirm --clean --onefile --console --name SaperServer --distpath dist --workpath build\server online.py
if errorlevel 1 (
  echo Server build failed.
  pause
  exit /b 1
)
echo Created: %~dp0dist\SaperServer.exe
pause