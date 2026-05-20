from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AppSettings:
    last_input_path: str = ""
    last_output_dir: str = ""
    bleed_mm: str = ""
    overlap_mm: str = ""
    overlap_mode: str = "Shared"
    dpi: str = ""
    export_format: str = "PDF"
    export_mode: str = "Raster"
    recent_files: list[str] | None = None
    recent_output_dirs: list[str] | None = None
    theme: str = "Professional Dark"
    window_geometry: str = ""


def default_settings_path() -> Path:
    return Path.home() / "AppData" / "Local" / "ArtboardCutter" / "settings.json"


def load_settings(path: Path | None = None) -> AppSettings:
    settings_path = path or default_settings_path()
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return AppSettings()
    settings = AppSettings(**{k: v for k, v in data.items() if k in AppSettings.__dataclass_fields__})
    if settings.recent_files is None:
        settings.recent_files = []
    if settings.recent_output_dirs is None:
        settings.recent_output_dirs = []
    return settings


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    settings_path = path or default_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
