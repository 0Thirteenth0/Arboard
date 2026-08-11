from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from .layout import compute_panel_layout
from .raster_export import choose_safe_raster_dpi
from .units import estimate_pixels, mm_to_pt


@dataclass(frozen=True)
class ExportEstimate:
    panel_count: int
    requested_dpi: int | None
    effective_dpi: int | None
    largest_panel_pixels: int
    estimated_raw_bytes: int
    estimated_disk_bytes: int
    uses_streaming_tiff: bool
    uses_bigtiff: bool
    free_disk_bytes: int | None
    warnings: tuple[str, ...]

    def summary_lines(self) -> list[str]:
        lines = [f"Panels: {self.panel_count}"]
        if self.requested_dpi:
            dpi_text = str(self.requested_dpi)
            if self.effective_dpi != self.requested_dpi:
                dpi_text += f" requested / {self.effective_dpi} effective"
            lines.append(f"DPI: {dpi_text}")
            lines.append(f"Largest panel: {self.largest_panel_pixels / 1e6:.1f} MP")
            lines.append(f"Raw image data: {format_bytes(self.estimated_raw_bytes)}")
            lines.append(f"Estimated output space: {format_bytes(self.estimated_disk_bytes)}")
        if self.uses_streaming_tiff:
            lines.append(f"TIFF writer: streamed {'BigTIFF' if self.uses_bigtiff else 'TIFF'}")
        if self.free_disk_bytes is not None:
            lines.append(f"Free disk space: {format_bytes(self.free_disk_bytes)}")
        lines.extend(f"Warning: {warning}" for warning in self.warnings)
        return lines


def format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def estimate_export_job(
    *,
    widths_mm: list[float],
    height_mm: float,
    bleed_mm: float,
    overlap_mm: float,
    overlap_mode: str,
    dpi: int | None,
    color_mode: str,
    export_format: str,
    preserve_vectors: bool,
    output_root: Path | None = None,
) -> ExportEstimate:
    layout, _, _ = compute_panel_layout(widths_mm, bleed_mm, overlap_mm, overlap_mode)
    free = None
    if output_root is not None:
        try:
            free = shutil.disk_usage(output_root).free
        except Exception:
            pass
    if preserve_vectors:
        return ExportEstimate(len(layout), None, None, 0, 0, 0, False, False, free, ())

    requested = int(dpi or 0)
    height_pt = mm_to_pt(height_mm + 2 * bleed_mm)
    sizes = [(mm_to_pt(panel.outer_width), height_pt) for panel in layout]
    streaming = export_format.lower() in {"tif", "tiff"}
    effective = requested if streaming else choose_safe_raster_dpi(sizes, requested, color_mode)[0]
    components = 4 if str(color_mode).upper() == "CMYK" else 3
    pixel_counts = [int(estimate_pixels(width, height_pt, effective)) for width, _height in sizes]
    largest = max(pixel_counts, default=0)
    raw = sum(pixel_counts) * components
    fmt = export_format.lower()
    disk_factor = 1.05 if fmt in {"tif", "tiff"} else (0.35 if fmt in {"jpg", "jpeg"} else 0.7)
    disk = int(raw * disk_factor)
    bigtiff = streaming and any(pixels * components >= 3_800_000_000 for pixels in pixel_counts)
    warnings = []
    if effective != requested:
        warnings.append(f"DPI will be reduced to {effective} for memory safety.")
    if free is not None and disk * 1.2 > free:
        warnings.append("Estimated output may exceed available disk space.")
    if raw > 2_000_000_000:
        warnings.append("This is a very large raster job and may take substantial time.")
    return ExportEstimate(len(layout), requested, effective, largest, raw, disk, streaming, bigtiff, free, tuple(warnings))
