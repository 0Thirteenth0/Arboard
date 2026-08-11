from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, fields
from pathlib import Path

from .profiles import ArtworkProfile
from .settings import default_app_data_dir


JOB_FILE_VERSION = 1


def default_recovery_job_path() -> Path:
    return default_app_data_dir() / "session-recovery.artboard-job.json"


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
    if payload.get("version") != JOB_FILE_VERSION or not isinstance(payload.get("profiles"), list):
        raise ValueError("Unsupported or invalid Artboard Cutter job file.")
    allowed = {field.name for field in fields(ArtworkProfile)}
    profiles = []
    for index, item in enumerate(payload["profiles"], 1):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid profile at position {index}.")
        values = {key: value for key, value in item.items() if key in allowed}
        try:
            profile = ArtworkProfile(**values)
            if not isinstance(profile.file_path, str) or not profile.file_path.strip():
                raise ValueError("source path is missing")
            profile.source_page_index = int(profile.source_page_index)
            profile.source_page_count = int(profile.source_page_count)
            if profile.source_page_index < 0 or profile.source_page_count < 1:
                raise ValueError("source page values are invalid")
            profile.color_mode = "CMYK" if str(profile.color_mode).upper() == "CMYK" else "RGB"
            profile.apply_export_mode_rules()
            profile.validate_output_name()
        except Exception as exc:
            raise ValueError(f"Invalid profile at position {index}: {exc}") from exc
        profiles.append(profile)
    if not profiles:
        raise ValueError("The job file does not contain any artwork profiles.")
    return profiles
