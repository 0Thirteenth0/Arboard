from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.artboard_cutter_core.version import APP_VERSION


def version_parts(version: str) -> tuple[int, int, int, int]:
    parts = version.split(".")
    if not 1 <= len(parts) <= 4 or any(not part.isdigit() for part in parts):
        raise ValueError(f"APP_VERSION must contain one to four numeric components: {version}")
    values = [int(part) for part in parts]
    return tuple((values + [0, 0, 0, 0])[:4])


def main() -> None:
    numeric = version_parts(APP_VERSION)
    version_tuple = ", ".join(str(value) for value in numeric)
    version_info = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_tuple}),
    prodvers=({version_tuple}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Artboard Cutter'),
          StringStruct('FileDescription', 'Large-format artwork panel export tool'),
          StringStruct('FileVersion', '{APP_VERSION}'),
          StringStruct('InternalName', 'ArtboardCutter'),
          StringStruct('OriginalFilename', 'ArtboardCutter.exe'),
          StringStruct('ProductName', 'Artboard Cutter'),
          StringStruct('ProductVersion', '{APP_VERSION}'),
        ],
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
"""
    (PROJECT_ROOT / "version_info.txt").write_text(version_info, encoding="utf-8")
    (PROJECT_ROOT / "installer" / "version.iss").write_text(
        f'#define MyAppVersion "{APP_VERSION}"\n',
        encoding="utf-8",
    )
    print(f"Generated release metadata for Artboard Cutter {APP_VERSION}")


if __name__ == "__main__":
    main()
