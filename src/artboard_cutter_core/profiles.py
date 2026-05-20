from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .illustrator_integration import get_illustrator_artboard_names
from .pdf_io import open_pdf_robust
from .units import fmt_mm

INVALID_OUTPUT_NAME_CHARS = set('<>:"/\\|?*')


@dataclass
class ArtworkProfile:
    """Session-only state for one queued artwork file."""

    file_path: str
    output_name: str = ""
    source_page_index: int = 0
    source_page_count: int = 1
    original_width_mm: float | None = None
    original_height_mm: float | None = None
    panel_widths: str = ""
    height_mm: str = ""
    bleed_mm: str = "0"
    overlap_mm: str = "0"
    overlap_mode: str = "Shared"
    dpi: str = "150"
    export_format: str = "PDF"
    export_mode: str = "Raster"
    preserve_vectors: bool = False
    vector_fit_mode: str = "stretch"
    output_status: str = "Ready"
    validation_state: str = "pending"
    selected: bool = False

    @property
    def file_name(self) -> str:
        return self.output_name or Path(self.file_path).stem

    @property
    def source_file_name(self) -> str:
        return Path(self.file_path).name

    def validate_output_name(self) -> None:
        validate_output_name(self.file_name)

    def original_size_label(self) -> str:
        if self.original_width_mm is None or self.original_height_mm is None:
            return "-"
        return f"{fmt_mm(self.original_width_mm)} x {fmt_mm(self.original_height_mm)} mm"

    def current_size_label(self) -> str:
        width = self.panel_widths.strip() or "-"
        height = self.height_mm.strip() or "-"
        return f"{width} x {height} mm"

    def reset_size_to_original(self) -> bool:
        if self.original_width_mm is None or self.original_height_mm is None:
            return False
        self.panel_widths = fmt_mm(self.original_width_mm)
        self.height_mm = fmt_mm(self.original_height_mm)
        self.validation_state = "pending"
        return True

    def apply_export_mode_rules(self) -> None:
        self.preserve_vectors = self.export_mode == "Vector"
        if self.preserve_vectors:
            self.export_format = "PDF"
            self.vector_fit_mode = "stretch"


def validate_output_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Output name cannot be empty.")
    if cleaned in {".", ".."}:
        raise ValueError("Output name cannot be '.' or '..'.")
    invalid = sorted({ch for ch in cleaned if ch in INVALID_OUTPUT_NAME_CHARS or ord(ch) < 32})
    if invalid:
        raise ValueError(f"Output name contains invalid character(s): {' '.join(invalid)}")
    return cleaned


def sanitize_output_name(name: str, fallback: str) -> str:
    cleaned = name.strip()
    chars = []
    for ch in cleaned:
        if ch in INVALID_OUTPUT_NAME_CHARS or ord(ch) < 32:
            chars.append("_")
        else:
            chars.append(ch)
    cleaned = "".join(chars).rstrip(" .")
    if not cleaned or cleaned in {".", ".."}:
        cleaned = fallback
    return validate_output_name(cleaned)


def _unique_output_names(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for name in names:
        count = seen.get(name, 0) + 1
        seen[name] = count
        result.append(name if count == 1 else f"{name}{count}")
    return result


def create_artwork_profiles(
    file_path: Path,
    *,
    bleed_mm: str = "0",
    overlap_mm: str = "0",
    overlap_mode: str = "Shared",
    dpi: str = "150",
    export_format: str = "PDF",
    export_mode: str = "Raster",
    artboard_names: list[str] | None = None,
    use_illustrator_names: bool = False,
) -> list[ArtworkProfile]:
    path = Path(file_path)
    doc = open_pdf_robust(path)
    profiles: list[ArtworkProfile] = []
    try:
        stem = path.stem
        page_count = max(1, int(doc.page_count))
        if artboard_names is None and use_illustrator_names:
            artboard_names = get_illustrator_artboard_names(path)
        if artboard_names and len(artboard_names) >= page_count:
            raw_names = artboard_names[:page_count]
        else:
            raw_names = [stem if page_count == 1 else f"{stem}{idx + 1}" for idx in range(page_count)]
        output_names = _unique_output_names(
            [sanitize_output_name(name, stem if page_count == 1 else f"{stem}{idx + 1}") for idx, name in enumerate(raw_names)]
        )
        for page_index in range(page_count):
            page = doc.load_page(page_index)
            rect = page.rect
            profile = ArtworkProfile(
                file_path=str(path),
                output_name=output_names[page_index],
                source_page_index=page_index,
                source_page_count=page_count,
                original_width_mm=float(rect.width * 25.4 / 72.0),
                original_height_mm=float(rect.height * 25.4 / 72.0),
                bleed_mm=bleed_mm,
                overlap_mm=overlap_mm,
                overlap_mode=overlap_mode,
                dpi=dpi,
                export_format=export_format,
                export_mode=export_mode,
                vector_fit_mode="stretch",
            )
            profile.apply_export_mode_rules()
            profile.reset_size_to_original()
            profiles.append(profile)
    finally:
        doc.close()
    return profiles
