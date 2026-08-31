"""Point packaged Tcl/Tk at the explicitly collected runtime libraries."""

import os
import sys
from pathlib import Path


bundle_root = Path(sys._MEIPASS)
tcl_library = bundle_root / "_tcl_data"
tk_library = bundle_root / "_tk_data"
if tcl_library.is_dir():
    os.environ["TCL_LIBRARY"] = str(tcl_library)
if tk_library.is_dir():
    os.environ["TK_LIBRARY"] = str(tk_library)
