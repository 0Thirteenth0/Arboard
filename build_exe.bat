@echo off
setlocal

REM Build Windows .exe for Artboard Cutter
REM Prereqs: Python 3.9+ installed and on PATH

echo [1/4] Upgrading pip (optional)...
python -m pip install --upgrade pip >nul 2>&1

echo [2/4] Installing build dependencies...
python -m pip install pyinstaller >nul 2>&1
if exist requirements.txt (
  python -m pip install -r requirements.txt
) else (
  python -m pip install PyMuPDF Pillow tkinterdnd2
)

echo [3/5] Generating application icon...
python tools\generate_icon.py

echo [4/5] Building executable...
pyinstaller --clean --noconfirm ArtboardCutter.spec

echo [5/5] Done.
echo Output: dist\ArtboardCutter.exe

endlocal
