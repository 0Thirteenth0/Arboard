@echo off
setlocal

REM Build Windows .exe for Artboard Cutter
REM Prereq: Python 3.10+ installed and on PATH

if not exist .venv\Scripts\python.exe (
  echo [1/5] Creating isolated build environment...
  python -m venv .venv
) else (
  echo [1/5] Using existing isolated build environment...
)

echo [2/5] Installing pinned build dependencies...
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b 1

echo [3/5] Generating application icon and version metadata...
.venv\Scripts\python.exe -c "import tkinter as tk; root = tk.Tk(); root.withdraw(); root.update_idletasks(); root.destroy()"
if errorlevel 1 (
  echo ERROR: Tkinter cannot initialize in the build environment.
  exit /b 1
)
.venv\Scripts\python.exe tools\generate_icon.py
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe tools\generate_version_metadata.py
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe tools\collect_licenses.py
if errorlevel 1 exit /b 1

echo [4/5] Building executable...
.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm ArtboardCutter.spec
if errorlevel 1 exit /b 1

echo [5/5] Done.
echo Output: dist\ArtboardCutter.exe

endlocal
