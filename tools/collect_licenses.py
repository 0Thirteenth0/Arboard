"""Collect unmodified dependency notices for Windows release packaging."""
from __future__ import annotations

from importlib import metadata
import json
from pathlib import Path
import shutil
import sys


DISTRIBUTIONS = (
    'PyMuPDF', 'Pillow', 'tkinterdnd2', 'pywin32', 'numpy',
    'tifffile', 'imagecodecs', 'pyinstaller',
)


def is_license_file(path: Path) -> bool:
    name = path.name.lower()
    return ('licenses' in (part.lower() for part in path.parts)
            or name in {'license', 'copying', 'notice', 'license.terms'}
            or name.startswith(('license.', 'license-', 'copying.', 'notice.')))


def collect_licenses(target: Path) -> dict:
    target.mkdir(parents=True, exist_ok=True)
    manifest = {'python': sys.version.split()[0], 'distributions': {}}
    for name in DISTRIBUTIONS:
        distribution = metadata.distribution(name)
        files = [p for p in (metadata.files(name) or []) if is_license_file(Path(p))]
        if not files:
            raise RuntimeError(f'No license files found for {name}')
        copied = []
        for file in files:
            relative = Path(file)
            if relative.is_absolute() or '..' in relative.parts:
                raise RuntimeError(f'Unsafe license path for {name}: {file}')
            source = Path(distribution.locate_file(file))
            destination = target / name / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            copied.append(destination.relative_to(target).as_posix())
        manifest['distributions'][name] = {
            'version': distribution.version, 'files': sorted(copied),
        }

    # CPython's combined license includes notices for its bundled libraries.
    runtime = Path(sys.base_prefix)
    runtime_files = [
        (runtime / 'LICENSE.txt', target / 'Python' / 'LICENSE.txt'),
        (runtime / 'tcl' / 'tk8.6' / 'license.terms', target / 'TclTk' / 'license.terms'),
    ]
    # TkDND's complete license is in its script header, not the Python wrapper license.
    dnd = metadata.distribution('tkinterdnd2')
    runtime_files.append((
        Path(dnd.locate_file('tkinterdnd2/tkdnd/win-x64/tkdnd.tcl')),
        target / 'TkDND' / 'tkdnd.tcl',
    ))
    for source, destination in runtime_files:
        if not source.is_file():
            raise RuntimeError(f'Required runtime license file is missing: {source}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    result = collect_licenses(root / 'build' / 'licenses')
    print(f"Collected notices for {len(result['distributions'])} distributions and Python/Tcl/Tk/TkDND")
