from __future__ import annotations

import math
from dataclasses import dataclass

from .modes import is_pdf_preserve_mode
from .profiles import validate_output_name


@dataclass(frozen=True)
class ValidatedExportValues:
    bleed_mm: float
    widths_mm: list[float]
    height_mm: float
    overlap_mm: float
    overlap_mode: str
    dpi: int
    export_format: str
    preserve_vectors: bool
    color_mode: str


def normalize_overlap_mode(mode: str) -> str:
    value = (mode or "shared").strip().lower().replace("-", "_").replace(" ", "_")
    return "left" if value in {"left", "left_only", "left_overlap"} else "shared"


def validate_export_values(
    *,
    output_name: str,
    bleed_mm: float,
    widths_mm: list[float],
    height_mm: float,
    overlap_mm: float,
    overlap_mode: str,
    dpi: int | None,
    export_format: str,
    export_mode: str | None = None,
    preserve_vectors: bool | None = None,
    color_mode: str = "RGB",
) -> ValidatedExportValues:
    validate_output_name(output_name)
    bleed = float(bleed_mm)
    widths = [float(width) for width in widths_mm]
    height = float(height_mm)
    overlap = float(overlap_mm)
    preserve = is_pdf_preserve_mode(export_mode or "") if preserve_vectors is None else bool(preserve_vectors)
    fmt = (export_format or "PDF").strip().lower()
    normalized_color_mode = "CMYK" if str(color_mode).strip().upper() == "CMYK" else "RGB"
    if fmt == "jpeg":
        fmt = "jpg"
    if fmt == "tiff":
        fmt = "tif"

    if not math.isfinite(bleed):
        raise ValueError("Bleed must be a finite number.")
    if any(not math.isfinite(width) for width in widths):
        raise ValueError("Panel widths must contain only finite numbers.")
    if not math.isfinite(height):
        raise ValueError("Height must be a finite number.")
    if not math.isfinite(overlap):
        raise ValueError("Overlap must be a finite number.")
    if bleed < 0:
        raise ValueError("Bleed must be 0 or greater.")
    if not widths or any(width <= 0 for width in widths):
        raise ValueError("Panel widths must contain one or more positive numbers.")
    if height <= 0:
        raise ValueError("Height must be greater than 0.")
    if overlap < 0:
        raise ValueError("Overlap must be 0 or greater.")
    if len(widths) > 1 and overlap >= min(widths):
        raise ValueError(
            f"Overlap ({overlap:g} mm) must be smaller than the narrowest panel ({min(widths):g} mm)."
        )
    if preserve:
        fmt = "pdf"
        dpi_value = int(dpi or 72)
    else:
        if dpi is None:
            raise ValueError("DPI is required for Raster export.")
        dpi_value = int(dpi)
        if dpi_value <= 0:
            raise ValueError("DPI must be greater than 0.")
        if fmt not in {"pdf", "jpg", "tif"}:
            raise ValueError(f"Unsupported Raster export format: {export_format}")

    return ValidatedExportValues(
        bleed_mm=bleed,
        widths_mm=widths,
        height_mm=height,
        overlap_mm=overlap,
        overlap_mode=normalize_overlap_mode(overlap_mode),
        dpi=dpi_value,
        export_format=fmt,
        preserve_vectors=preserve,
        color_mode=normalized_color_mode,
    )
