@echo off
setlocal

REM Build Windows .exe for Artboard Cutter (onedir by default)
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

echo [3/4] Building executable (onedir)...
pyinstaller --clean --noconfirm --noconsole ^
  --name "ArtboardCutter" ^
  --collect-all fitz ^
  --collect-all PIL ^
  --collect-all tkinterdnd2 ^
  artboard_cutter_gui_advanced.py

echo [4/4] Done.
echo Output (folder): dist\ArtboardCutter\ArtboardCutter.exe
echo To build a single-file exe, rerun with --onefile:
echo   pyinstaller --clean --noconfirm --noconsole --onefile --name "ArtboardCutter" --collect-all fitz --collect-all PIL --collect-all tkinterdnd2 artboard_cutter_gui_advanced.py

endlocal
