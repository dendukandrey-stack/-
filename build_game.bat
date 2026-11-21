@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (set "PYTHON=python") else (set "PYTHON=py -3")
%PYTHON% -m PyInstaller --noconfirm --clean --onefile --windowed --name Saper --distpath dist --workpath build\game main.py
if errorlevel 1 (
  echo Game build failed.
  pause
  exit /b 1
)
echo Created: %~dp0dist\Saper.exe
pause