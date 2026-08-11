PDF_PRESERVE_EXPORT_MODE = "PDF Preserve"


def normalize_export_mode(mode: str) -> str:
    value = (mode or "").strip().lower().replace("_", " ").replace("-", " ")
    if value in {"vector", "pdf preserve", "preserve", "pdf passthrough", "pdf embedded", "pdf fast"}:
        return PDF_PRESERVE_EXPORT_MODE
    return "Raster"


def is_pdf_preserve_mode(mode: str) -> bool:
    return normalize_export_mode(mode) == PDF_PRESERVE_EXPORT_MODE
