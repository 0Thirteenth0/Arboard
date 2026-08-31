from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProfileExportValues:
    bleed_mm: float
    widths_mm: list[float]
    height_mm: float
    overlap_mm: float
    overlap_mode: str
    dpi: int
    export_format: str
    preserve_vectors: bool
    color_mode: str
    icc_mode: str
    icc_profile_path: str
    rendering_intent: str


@dataclass(frozen=True)
class PendingExportJob:
    iid: str
    source_path: Path
    output_name: str
    page_index: int
    values: ProfileExportValues
