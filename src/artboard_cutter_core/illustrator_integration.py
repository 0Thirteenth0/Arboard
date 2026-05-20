from __future__ import annotations

import json
import csv
import io
import subprocess
import sys
from pathlib import Path


def get_illustrator_artboard_names(
    file_path: Path,
    timeout_seconds: int = 45,
    require_running: bool = False,
) -> list[str] | None:
    """Return Illustrator artboard names through COM when available.

    This is intentionally optional. PyMuPDF reads the PDF-compatible layer of
    `.ai` files, but Illustrator artboard names usually live in Illustrator's
    own document model. On Windows with Adobe Illustrator and pywin32 installed,
    COM automation can open the document and read those names directly.
    """

    path = Path(file_path)
    if path.suffix.lower() != ".ai" or not sys.platform.startswith("win"):
        return None
    if require_running and not _illustrator_process_ids():
        return None

    if timeout_seconds and timeout_seconds > 0 and not getattr(sys, "frozen", False):
        return _get_illustrator_artboard_names_subprocess(path, timeout_seconds, require_running=require_running)

    return _get_illustrator_artboard_names_direct(path)


def _get_illustrator_artboard_names_subprocess(
    path: Path,
    timeout_seconds: int,
    require_running: bool = False,
) -> list[str] | None:
    existing_pids = _illustrator_process_ids()
    if require_running and not existing_pids:
        return None
    script = (
        "import json, sys; "
        "from pathlib import Path; "
        "from src.artboard_cutter_core.illustrator_integration import _get_illustrator_artboard_names_direct; "
        "names=_get_illustrator_artboard_names_direct(Path(sys.argv[1])); "
        "print(json.dumps(names))"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", script, str(path.resolve())],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _terminate_new_illustrator_processes(existing_pids)
        return None
    except Exception:
        return None

    if result.returncode != 0:
        return None
    try:
        names = json.loads(result.stdout.strip() or "null")
    except Exception:
        return None
    if isinstance(names, list):
        return [str(name) for name in names]
    return None


def _illustrator_process_ids() -> set[int]:
    if not sys.platform.startswith("win"):
        return set()
    try:
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return set()
    if result.returncode != 0:
        return set()
    pids: set[int] = set()
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) < 2:
            continue
        image_name = row[0].lower()
        if "illustrator" not in image_name:
            continue
        try:
            pids.add(int(row[1]))
        except ValueError:
            pass
    return pids


def _terminate_new_illustrator_processes(existing_pids: set[int]) -> None:
    current_pids = _illustrator_process_ids()
    for pid in sorted(current_pids - existing_pids):
        try:
            subprocess.run(
                ["taskkill", "/pid", str(pid), "/t", "/f"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception:
            pass


def _get_illustrator_artboard_names_direct(path: Path) -> list[str] | None:
    path = Path(path)
    if path.suffix.lower() != ".ai" or not sys.platform.startswith("win"):
        return None

    try:
        import win32com.client  # type: ignore
    except Exception:
        return None

    app = None
    doc = None
    previous_interaction_level = None
    try:
        app = win32com.client.Dispatch("Illustrator.Application")
        try:
            previous_interaction_level = app.UserInteractionLevel
            # UserInteractionLevel.DONTDISPLAYALERTS. This lets Illustrator
            # ignore missing-link prompts while we only inspect artboard names.
            app.UserInteractionLevel = -1
        except Exception:
            previous_interaction_level = None
        doc = app.Open(str(path.resolve()))
        artboards = doc.Artboards
        count = int(artboards.Count)
        names: list[str] = []
        for idx in range(1, count + 1):
            names.append(str(artboards.Item(idx).Name))
        return names
    except Exception:
        return None
    finally:
        if doc is not None:
            try:
                # Illustrator SaveOptions.aiDoNotSaveChanges is 2.
                doc.Close(2)
            except Exception:
                try:
                    doc.Close()
                except Exception:
                    pass
        if app is not None and previous_interaction_level is not None:
            try:
                app.UserInteractionLevel = previous_interaction_level
            except Exception:
                pass
