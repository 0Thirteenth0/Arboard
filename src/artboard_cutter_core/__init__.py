"""Public API for the Artboard Cutter engine, loaded lazily by module."""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "ArtworkProfile": ("profiles", "ArtworkProfile"),
    "ExportCancelled": ("errors", "ExportCancelled"),
    "ExportError": ("errors", "ExportError"),
    "ExportOptions": ("export", "ExportOptions"),
    "ExportResult": ("export", "ExportResult"),
    "PDF_PRESERVE_EXPORT_MODE": ("modes", "PDF_PRESERVE_EXPORT_MODE"),
    "PT_PER_MM": ("units", "PT_PER_MM"),
    "PanelLayout": ("layout", "PanelLayout"),
    "add_evenly_distributed_panel": ("layout", "add_evenly_distributed_panel"),
    "compute_panel_layout": ("layout", "compute_panel_layout"),
    "compute_scale_matrix": ("units", "compute_scale_matrix"),
    "create_artwork_profiles": ("profiles", "create_artwork_profiles"),
    "estimate_pixels": ("units", "estimate_pixels"),
    "fmt_mm": ("units", "fmt_mm"),
    "force_page_boxes": ("pdf_io", "force_page_boxes"),
    "is_pdf_preserve_mode": ("modes", "is_pdf_preserve_mode"),
    "mm_to_pt": ("units", "mm_to_pt"),
    "normalize_export_mode": ("modes", "normalize_export_mode"),
    "open_pdf_robust": ("pdf_io", "open_pdf_robust"),
    "parse_widths_list": ("layout", "parse_widths_list"),
    "process_file": ("export", "process_file"),
    "pt_to_mm": ("units", "pt_to_mm"),
    "redistribute_panel_widths": ("layout", "redistribute_panel_widths"),
    "resize_adjacent_panel_widths": ("layout", "resize_adjacent_panel_widths"),
    "sanitize_output_name": ("profiles", "sanitize_output_name"),
    "split_last_panel_width": ("layout", "split_last_panel_width"),
    "validate_output_name": ("profiles", "validate_output_name"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
