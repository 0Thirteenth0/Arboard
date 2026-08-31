from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .modes import normalize_export_mode


EXPORT_PRESET_FIELDS = (
    "bleed_mm",
    "overlap_mm",
    "overlap_mode",
    "dpi",
    "color_mode",
    "export_format",
    "export_mode",
    "icc_mode",
    "icc_profile_path",
    "rendering_intent",
)

_WINDOW_GEOMETRY_PATTERN = re.compile(r"^[1-9]\d*x[1-9]\d*(?:[+-]\d+[+-]\d+)?$")


def normalize_export_presets(presets) -> dict[str, dict[str, str]]:
    """Keep presets limited to reusable export behavior, never artwork paths or dimensions."""
    if not isinstance(presets, dict):
        return {}
    normalized = {}
    for name, values in presets.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(values, dict):
            continue
        normalized[name] = {
            key: str(values[key])
            for key in EXPORT_PRESET_FIELDS
            if key in values and values[key] is not None
        }
    return normalized


@dataclass
class AppSettings:
    last_input_path: str = ""
    last_output_dir: str = ""
    bleed_mm: str = "0"
    overlap_mm: str = "0"
    overlap_mode: str = "Shared"
    dpi: str = "150"
    color_mode: str = "RGB"
    export_format: str = "PDF"
    export_mode: str = "Raster"
    icc_mode: str = "Off"
    icc_profile_path: str = ""
    rendering_intent: str = "Perceptual"
    recent_files: list[str] | None = None
    recent_output_dirs: list[str] | None = None
    presets: dict[str, dict[str, str]] | None = None
    theme: str = "Soft Blue"
    window_geometry: str = ""


def default_app_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "ArtboardCutter"
    return Path.home() / ".artboard_cutter"


def default_settings_path() -> Path:
    return default_app_data_dir() / "settings.json"


def default_log_dir() -> Path:
    return default_app_data_dir() / "logs"


def default_output_dir() -> Path:
    documents = Path.home() / "Documents"
    return (documents if documents.exists() else Path.home()) / "Artboard Cutter Exports"


def load_settings(path: Path | None = None) -> AppSettings:
    settings_path = path or default_settings_path()
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return AppSettings()
    if not isinstance(data, dict):
        return AppSettings()
    values = {k: v for k, v in data.items() if k in AppSettings.__dataclass_fields__}
    collection_fields = {"recent_files", "recent_output_dirs", "presets"}
    for key in list(values):
        if key not in collection_fields and not isinstance(values[key], str):
            values.pop(key)
    settings = AppSettings(**values)
    settings.recent_files = (
        [item for item in settings.recent_files if isinstance(item, str) and item.strip()]
        if isinstance(settings.recent_files, list)
        else []
    )
    settings.recent_output_dirs = (
        [item for item in settings.recent_output_dirs if isinstance(item, str) and item.strip()]
        if isinstance(settings.recent_output_dirs, list)
        else []
    )
    settings.presets = normalize_export_presets(settings.presets)
    settings.color_mode = "CMYK" if str(settings.color_mode).upper() == "CMYK" else "RGB"
    settings.export_mode = normalize_export_mode(settings.export_mode)
    if settings.window_geometry and not _WINDOW_GEOMETRY_PATTERN.fullmatch(settings.window_geometry):
        settings.window_geometry = ""
    return settings


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    settings_path = path or default_settings_path()
    settings.export_mode = normalize_export_mode(settings.export_mode)
    settings.presets = normalize_export_presets(settings.presets)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(settings), indent=2)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{settings_path.name}.",
            suffix=".tmp",
            dir=settings_path.parent,
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, settings_path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
