from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path


class OutputConflictError(RuntimeError):
    """Raised when an export would overwrite files without permission."""


def normalized_extension(export_fmt: str, preserve_vectors: bool = False) -> str:
    if preserve_vectors:
        return "pdf"
    value = (export_fmt or "pdf").strip().lower()
    if value == "jpeg":
        return "jpg"
    if value == "tiff":
        return "tif"
    if value not in {"pdf", "jpg", "tif"}:
        raise ValueError(f"Unsupported export format: {export_fmt}")
    return value


def build_output_paths(
    output_root: Path,
    base_name: str,
    panel_count: int,
    export_fmt: str,
    *,
    preserve_vectors: bool = False,
) -> list[Path]:
    if panel_count < 1:
        raise ValueError("At least one output panel is required.")
    extension = normalized_extension(export_fmt, preserve_vectors)
    root = Path(output_root)
    return [root / f"{base_name}_{index}.{extension}" for index in range(1, panel_count + 1)]


def find_stale_panel_outputs(output_paths: list[Path]) -> list[Path]:
    """Find numbered sibling panel files not present in the planned output set."""
    if not output_paths:
        return []
    first = output_paths[0]
    match = re.match(r"^(.*)_1(\.[^.]+)$", first.name, flags=re.IGNORECASE)
    if not match or not first.parent.exists():
        return []
    prefix, suffix = match.groups()
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+){re.escape(suffix)}$", re.IGNORECASE)
    planned = {os.path.normcase(str(path.resolve())) for path in output_paths}
    stale = []
    for candidate in first.parent.iterdir():
        if candidate.is_file() and pattern.match(candidate.name):
            key = os.path.normcase(str(candidate.resolve()))
            if key not in planned:
                stale.append(candidate)
    return sorted(stale, key=lambda path: path.name.casefold())


def find_duplicate_paths(paths: list[Path]) -> list[Path]:
    seen: dict[str, Path] = {}
    duplicates: list[Path] = []
    for path in paths:
        key = os.path.normcase(os.path.abspath(str(path)))
        if key in seen:
            duplicates.append(path)
        else:
            seen[key] = path
    return duplicates


@dataclass
class StagedOutputSet:
    """Write a complete panel set before replacing any final output files."""

    final_paths: list[Path]
    overwrite: bool = False
    cleanup_stale: bool = False

    def __post_init__(self) -> None:
        if not self.final_paths:
            raise ValueError("No output paths were provided.")
        duplicates = find_duplicate_paths(self.final_paths)
        if duplicates:
            raise OutputConflictError(f"Duplicate output path: {duplicates[0]}")
        existing = [path for path in self.final_paths if path.exists()]
        if existing and not self.overwrite:
            raise OutputConflictError(f"Output already exists: {existing[0]}")

        token = uuid.uuid4().hex
        self.stage_paths = [
            path.with_name(f".{path.stem}.{token}.tmp{path.suffix}")
            for path in self.final_paths
        ]
        self._backup_paths = [
            path.with_name(f".{path.name}.{token}.backup")
            for path in self.final_paths
        ]

    def __enter__(self) -> "StagedOutputSet":
        for path in self.final_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
        return self

    def commit(self) -> None:
        missing = [path for path in self.stage_paths if not path.exists()]
        if missing:
            raise RuntimeError(f"Export did not create staged output: {missing[0]}")
        if not self.overwrite:
            conflicts = [path for path in self.final_paths if path.exists()]
            if conflicts:
                raise OutputConflictError(f"Output appeared during export: {conflicts[0]}")

        backed_up: list[tuple[Path, Path]] = []
        installed: list[Path] = []
        try:
            for final, backup in zip(self.final_paths, self._backup_paths, strict=True):
                if final.exists():
                    final.replace(backup)
                    backed_up.append((final, backup))
            for stage, final in zip(self.stage_paths, self.final_paths, strict=True):
                stage.replace(final)
                installed.append(final)
        except Exception:
            for final in installed:
                try:
                    final.unlink(missing_ok=True)
                except Exception:
                    pass
            for final, backup in reversed(backed_up):
                try:
                    backup.replace(final)
                except Exception:
                    pass
            raise
        else:
            for _, backup in backed_up:
                try:
                    backup.unlink(missing_ok=True)
                except OSError:
                    # The new panel set is installed. A locked backup is safer
                    # left for manual cleanup than turning a successful export
                    # into an apparent failure.
                    pass
            if self.cleanup_stale:
                for stale in find_stale_panel_outputs(self.final_paths):
                    try:
                        stale.unlink(missing_ok=True)
                    except OSError:
                        pass

    def cleanup(self) -> None:
        # Never delete backup files here. If rollback could not restore one,
        # the hidden backup is the only recoverable copy of the old output.
        for path in self.stage_paths:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.cleanup()
