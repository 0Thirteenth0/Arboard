from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import asdict, fields
from pathlib import Path

from .profiles import ArtworkProfile
from .settings import default_app_data_dir


JOB_FILE_VERSION = 1
JOB_FILE_EXTENSION = ".artboard-job"
LEGACY_JOB_FILE_EXTENSION = ".artboard-job.json"

_PROFILE_STRING_FIELDS = {
    "file_path",
    "output_name",
    "panel_widths",
    "height_mm",
    "bleed_mm",
    "overlap_mm",
    "overlap_mode",
    "dpi",
    "color_mode",
    "icc_mode",
    "icc_profile_path",
    "rendering_intent",
    "export_format",
    "raster_export_format",
    "export_mode",
    "vector_fit_mode",
    "output_status",
    "validation_state",
}


def default_recovery_job_path() -> Path:
    return default_app_data_dir() / "session-recovery.artboard-job.json"


def is_job_file_path(path: str | Path) -> bool:
    name = Path(path).name.casefold()
    return name.endswith(JOB_FILE_EXTENSION) or name.endswith(LEGACY_JOB_FILE_EXTENSION)


def startup_job_path(arguments: list[str]) -> Path | None:
    """Return the job document passed by Explorer or a command-line launch."""
    for argument in arguments:
        if argument and not argument.startswith("-") and is_job_file_path(argument):
            return Path(argument).expanduser()
    return None


def save_job(path: Path, profiles: list[ArtworkProfile]) -> None:
    job_path = Path(path)
    if not profiles:
        raise ValueError("The artwork queue is empty.")
    payload = {
        "version": JOB_FILE_VERSION,
        "profiles": [asdict(profile) for profile in profiles],
    }
    job_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{job_path.name}.",
            suffix=".tmp",
            dir=job_path.parent,
            delete=False,
        ) as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, job_path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def load_job(path: Path) -> list[ArtworkProfile]:
    job_path = Path(path)
    try:
        payload = json.loads(job_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Could not read job file: {exc}") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("version") != JOB_FILE_VERSION
        or not isinstance(payload.get("profiles"), list)
    ):
        raise ValueError("Unsupported or invalid Artboard Cutter job file.")
    allowed = {field.name for field in fields(ArtworkProfile)}
    profiles = []
    for index, item in enumerate(payload["profiles"], 1):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid profile at position {index}.")
        values = {key: value for key, value in item.items() if key in allowed}
        try:
            profile = ArtworkProfile(**values)
            for field_name in _PROFILE_STRING_FIELDS:
                if not isinstance(getattr(profile, field_name), str):
                    raise ValueError(f"{field_name} must be text")
            if not profile.file_path.strip():
                raise ValueError("source path is missing")
            if isinstance(profile.source_page_index, bool) or not isinstance(profile.source_page_index, int):
                raise ValueError("source_page_index must be a whole number")
            if isinstance(profile.source_page_count, bool) or not isinstance(profile.source_page_count, int):
                raise ValueError("source_page_count must be a whole number")
            if (
                profile.source_page_index < 0
                or profile.source_page_count < 1
                or profile.source_page_index >= profile.source_page_count
            ):
                raise ValueError("source page values are invalid")
            if not isinstance(profile.selected, bool):
                raise ValueError("selected must be true or false")
            if not isinstance(profile.preserve_vectors, bool):
                raise ValueError("preserve_vectors must be true or false")
            for field_name in ("original_width_mm", "original_height_mm"):
                dimension = getattr(profile, field_name)
                if dimension is not None:
                    if isinstance(dimension, bool) or not isinstance(dimension, (int, float)):
                        raise ValueError(f"{field_name} must be a number or null")
                    dimension = float(dimension)
                    if not math.isfinite(dimension) or dimension <= 0:
                        raise ValueError(f"{field_name} must be a positive finite number")
                    setattr(profile, field_name, dimension)
            profile.color_mode = "CMYK" if str(profile.color_mode).upper() == "CMYK" else "RGB"
            profile.apply_export_mode_rules()
            profile.validate_output_name()
        except Exception as exc:
            raise ValueError(f"Invalid profile at position {index}: {exc}") from exc
        profiles.append(profile)
    if not profiles:
        raise ValueError("The job file does not contain any artwork profiles.")
    return profiles
