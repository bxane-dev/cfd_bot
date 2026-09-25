@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title CFD Bot - Release Builder

echo ============================================================
echo   CFD Bot Windows Release Builder
echo ============================================================
echo.

where node >nul 2>&1 || (
  echo Node.js is required. Install Node.js 22+ and run this again.
  exit /b 1
)
where npm >nul 2>&1 || (
  echo npm is required.
  exit /b 1
)
where python >nul 2>&1 || (
  echo Python 3.11+ is required.
  exit /b 1
)

echo [1/5] Installing Python build tools...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt pyinstaller pillow
if errorlevel 1 exit /b 1

echo [2/5] Generating Windows app icon...
python desktop\make_icon.py
if errorlevel 1 exit /b 1

echo [3/5] Installing Electron dependencies...
call npm install
if errorlevel 1 exit /b 1

echo [4/5] Bundling Python backend...
if exist dist_backend rmdir /s /q dist_backend
if exist build\pyinstaller rmdir /s /q build\pyinstaller
python -m PyInstaller --noconfirm --clean --distpath dist_backend --workpath build\pyinstaller desktop\backend.spec
if errorlevel 1 exit /b 1

echo [5/5] Building Windows installer...
call npm run dist
if errorlevel 1 exit /b 1

echo.
echo ============================================================
echo Build complete.
echo Installer output: %CD%\release
echo ============================================================
exit /b 0
