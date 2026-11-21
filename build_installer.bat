@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (set "PYTHON=python") else (set "PYTHON=py -3")
%PYTHON% -m PyInstaller --noconfirm --clean --onefile --windowed --name SaperInstaller --distpath dist --workpath build\installer installer.py
if errorlevel 1 (
  echo Installer build failed.
  pause
  exit /b 1
)
echo Created: %~dp0dist\SaperInstaller.exe
pause