"""Collect Tcl/Tk explicitly for Windows standalone-Python layouts."""

import sys
from pathlib import Path


python_root = Path(sys.base_prefix)
dll_root = python_root / "DLLs"
tcl_root = python_root / "tcl"

binaries = [
    (str(path), ".")
    for path in (dll_root / "_tkinter.pyd", dll_root / "tcl86t.dll", dll_root / "tk86t.dll")
    if path.is_file()
]

datas = []
for source, destination in (
    (tcl_root / "tcl8.6", "_tcl_data"),
    (tcl_root / "tk8.6", "_tk_data"),
    (tcl_root / "tcl8", "tcl8"),
):
    if source.is_dir():
        datas.append((str(source), destination))
