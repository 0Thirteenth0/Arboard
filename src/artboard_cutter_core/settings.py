from __future__ import annotations

import json
import os
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


def normalize_layout_templates(templates) -> dict[str, dict[str, object]]:
    """Validate reusable panel proportions without coupling them to artwork dimensions."""
    if not isinstance(templates, dict):
        return {}
    normalized = {}
    for name, values in templates.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(values, dict):
            continue
        try:
            ratios = [float(value) for value in values.get("ratios", [])]
        except (TypeError, ValueError):
            continue
        total = sum(ratios)
        if not ratios or total <= 0 or any(value <= 0 for value in ratios):
            continue
        normalized[name.strip()] = {"ratios": [value / total for value in ratios]}
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
    layout_templates: dict[str, dict[str, object]] | None = None
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
    settings = AppSettings(**{k: v for k, v in data.items() if k in AppSettings.__dataclass_fields__})
    if not isinstance(settings.recent_files, list):
        settings.recent_files = []
    if not isinstance(settings.recent_output_dirs, list):
        settings.recent_output_dirs = []
    settings.presets = normalize_export_presets(settings.presets)
    settings.layout_templates = normalize_layout_templates(settings.layout_templates)
    settings.color_mode = "CMYK" if str(settings.color_mode).upper() == "CMYK" else "RGB"
    settings.export_mode = normalize_export_mode(settings.export_mode)
    return settings


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    settings_path = path or default_settings_path()
    settings.export_mode = normalize_export_mode(settings.export_mode)
    settings.presets = normalize_export_presets(settings.presets)
    settings.layout_templates = normalize_layout_templates(settings.layout_templates)
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
