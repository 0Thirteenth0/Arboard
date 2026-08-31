"""Keep tkinter discoverable when PyInstaller misdetects standalone Python 3.14 Tk."""


def pre_find_module_path(_hook_api):
    # Tk is validated by the build script before PyInstaller runs. The bundled
    # pre-find hook can incorrectly mark the Python Install Manager layout as
    # broken, so leave the interpreter's normal tkinter search path intact.
    return None
